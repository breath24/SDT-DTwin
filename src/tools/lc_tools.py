from __future__ import annotations

from pathlib import Path
from typing import Optional, List, Dict, Any
import json
from datetime import datetime

from langchain_core.tools import tool
from ..config_loader import load_config, get_timeout_setting

from .fs import read_file_text as _read, write_file_text as _write, list_directory as _ls, search_ripgrep as _search
from .shell import run_shell as _run, run_shell_stream as _run_stream
import re as _re
from .patch_apply import process_patch_in_repo, DiffError as _PatchDiffError

def _abs(repo_dir: Path, rel: str) -> str:
    p = repo_dir / rel
    return str(p)


def make_read_tool(repo_dir: Path):
    @tool("read_file", return_direct=False)
    def read_file(path, line_start: int | None = None, line_end: int | None = None) -> str:
        """Read a UTF-8 text file relative to the repository root.

        Optional line slicing:
        - line_start: 1-based start line (inclusive)
        - line_end: 1-based end line (inclusive)
        If either is provided, returns only that slice; otherwise returns full content.
        """
        try:
            text = _read(_abs(repo_dir, str(path)))
        except FileNotFoundError:
            return f"NOT_FOUND: {path}"
        except Exception as e:
            return f"ERROR: {e}"

        # If no slicing requested, return full text
        if line_start is None and line_end is None:
            return text

        try:
            # Normalize indices (1-based inclusive)
            lines = text.splitlines()
            start_idx = 1 if line_start is None else max(1, int(line_start))
            end_idx = len(lines) if line_end is None else max(1, int(line_end))
            if start_idx > end_idx:
                start_idx, end_idx = end_idx, start_idx
            # Convert to 0-based slice with inclusive end
            start0 = start_idx - 1
            end0 = end_idx
            return "\n".join(lines[start0:end0])
        except Exception as e:
            return f"ERROR: bad line range: {e}"

    return read_file


def make_write_tool(repo_dir: Path):
    @tool("write_file", return_direct=False)
    def write_file(path, content: str) -> str:
        """Write UTF-8 content to a file relative to the repository root, creating parents.

        Notes:
        -  Always provide a full relative path using forward slashes. Forward slashes are normalized.
        - The file will be written exactly at the provided relative path under the repo root.
        """
        p = str(path).replace("\\", "/")
        try:
            _write(_abs(repo_dir, p), content)
        except FileNotFoundError:
            # ensure parent exists
            abs_path = Path(_abs(repo_dir, p))
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            _write(str(abs_path), content)
        return f"WROTE {p} ({len(content)} bytes)"

    return write_file


def make_list_tool(repo_dir: Path):
    @tool("list_dir", return_direct=False)
    def list_dir(path = ".") -> str:
        """List directory entries relative to the repository root."""
        entries = _ls(_abs(repo_dir, str(path)))
        return "\n".join(entries)

    return list_dir


def make_search_tool(repo_dir: Path):
    @tool("search", return_direct=False)
    def search(pattern: str, path = ".") -> str:
        """Search files for a pattern using ripgrep if available, else Python fallback."""
        return _search(pattern, _abs(repo_dir, str(path)))

    return search


def make_shell_tool(repo_dir: Path, docker: Optional[Dict[str, Any]] = None, config: Optional[Any] = None):
    @tool("shell", return_direct=False)
    def shell(command: str, timeout: Optional[int] = None, stdin: Optional[str] = None, stream: bool = False) -> str:
        """Run a shell command in the repository root.

        Guidance:
        - Prefer non-interactive flags (e.g., --yes/-y/--non-interactive, CI=1)
        - If unavoidable, provide input via `stdin` or set `stream=true` to capture live output.
        - Timeouts are seconds; defaults to 60s, capped to 600s (10m).
        """
        # Default and cap timeout
        actual_config = config if config is not None else load_config()
        default_timeout = get_timeout_setting(actual_config, "default_shell_timeout", 60)
        max_timeout = get_timeout_setting(actual_config, "max_shell_timeout", 600)
        
        if timeout is None:
            timeout = default_timeout
        try:
            timeout = int(timeout)
        except Exception:
            timeout = default_timeout
        timeout = max(1, min(timeout, max_timeout))
        if docker and docker.get("container_id"):
            container_id = docker["container_id"]
            temp_config = actual_config
            workdir = docker.get("workdir", temp_config.docker.get("workspace_dir", "/workspace"))
            # Execute inside container with POSIX shell
            exec_cmd = f"docker exec -w {workdir} {container_id} sh -lc \"{command}\""
            if stream:
                code, combined = _run_stream(exec_cmd, cwd=str(repo_dir), timeout=timeout)
                return f"$ {command}\n[exit {code}]\n{combined}"
            code, out, err = _run(exec_cmd, cwd=str(repo_dir), timeout=timeout, stdin=stdin)
            return f"$ {command}\n[exit {code}]\n{out or err}"
        if stream:
            code, combined = _run_stream(command, cwd=str(repo_dir), timeout=timeout)
            return f"$ {command}\n[exit {code}]\n{combined}"
        code, out, err = _run(command, cwd=str(repo_dir), timeout=timeout, stdin=stdin)
        return f"$ {command}\n[exit {code}]\n{out or err}"

    return shell

def make_apply_patch_tool(repo_dir: Path):
    @tool("apply_patch", return_direct=False)
    def apply_patch(patch_text: str) -> str:
        """Apply a V4A-style multi-file patch to the repository.

        Input must start with '*** Begin Patch' and end with '*** End Patch'. Paths must be relative.
        Returns 'Done!' on success or an error string starting with 'ERROR:' on failure.
        """
        try:
            # Add debugging info
            abs_repo_dir = repo_dir.resolve()
            if not abs_repo_dir.exists():
                return f"ERROR: Repository directory does not exist: {abs_repo_dir}"
            
            # Debug: Check if patch format is correct
            if not patch_text.strip().startswith('*** Begin Patch'):
                return (
                    "ERROR: Patch must start with '*** Begin Patch' and end with '*** End Patch'.\n"
                    "Tips: Make smaller patches (5-10 lines), read the file right before patching, and use exact context.\n"
                    "Fallback: use replace_in_file or replace_region for targeted edits."
                )
            
            # Extract file paths from patch for better error reporting
            lines = patch_text.split('\n')
            file_paths = []
            for line in lines:
                if line.startswith('*** Update File: ') or line.startswith('*** Add File: '):
                    file_path = line.split(': ', 1)[1].strip()
                    file_paths.append(file_path)
            
            # Debug: Show what files we're trying to patch
            if not file_paths:
                return (
                    "ERROR: No files found in patch. Ensure you include lines like '*** Update File: path/to/file'.\n"
                    "Fallback: consider replace_in_file(path, pattern, replacement) for small changes."
                )
            
            # Check if files exist for Update operations
            for file_path in file_paths:
                if any(line.startswith(f'*** Update File: {file_path}') for line in lines):
                    full_path = abs_repo_dir / file_path
                    if not full_path.exists():
                        # List what files DO exist in that directory
                        try:
                            parent_dir = full_path.parent
                            if parent_dir.exists():
                                existing_files = [f.name for f in parent_dir.iterdir() if f.is_file()]
                                return f"ERROR: File not found: {file_path} in {abs_repo_dir}. Files in {parent_dir}: {existing_files}"
                            else:
                                return f"ERROR: Directory not found: {parent_dir} (for file {file_path})"
                        except Exception:
                            return (
                                f"ERROR: File not found: {file_path} in {abs_repo_dir}.\n"
                                "Tip: Verify the relative path and use forward slashes."
                            )
            
            res = process_patch_in_repo(repo_dir, patch_text)
            return res
        except _PatchDiffError as e:
            # Enhanced error message with suggestions
            error_msg = str(e)
            suggestions = []
            
            if "Invalid Context" in error_msg or "Invalid EOF Context" in error_msg:
                suggestions.append("File changed or context drifted. Read the file again immediately before patching.")
                suggestions.append("Use smaller hunks (5-10 lines) with exact surrounding context.")
                suggestions.append("Avoid non-ASCII punctuation in context; prefer plain ASCII.")
                suggestions.append("Fallback to replace_in_file or replace_region for surgical changes.")
            
            enhanced_msg = f"ERROR: Patch format error: {e}"
            if suggestions:
                enhanced_msg += "\n\nSuggestions:\n" + "\n".join(f"- {s}" for s in suggestions)
            
            return enhanced_msg
        except Exception as e:
            return f"ERROR: Unexpected error: {e}"

    return apply_patch


def make_debug_tool(repo_dir: Path):
    @tool("debug_env", return_direct=False)
    def debug_env() -> str:
        """Debug tool to show current working environment and file structure."""
        try:
            abs_repo_dir = repo_dir.resolve()
            info = []
            info.append(f"Repository directory: {abs_repo_dir}")
            info.append(f"Directory exists: {abs_repo_dir.exists()}")
            
            if abs_repo_dir.exists():
                files = []
                for item in abs_repo_dir.iterdir():
                    if item.is_file():
                        files.append(f"  FILE: {item.name}")
                    elif item.is_dir():
                        files.append(f"  DIR:  {item.name}/")
                info.append(f"Contents ({len(files)} items):")
                info.extend(files[:10])  # Limit to first 10 items
                if len(files) > 10:
                    info.append(f"  ... and {len(files) - 10} more items")
            
            return "\n".join(info)
        except Exception as e:
            return f"ERROR: {e}"
    
    return debug_env


def make_lint_tool(
    repo_dir: Path,
    analysis: Optional[Dict[str, Any]] = None,
    docker: Optional[Dict[str, Any]] = None,
    config: Optional[Any] = None,
):
    @tool("lint", return_direct=False)
    def lint(command: str = "", timeout: Optional[int] = None) -> str:
        """Run linter(s) for the project.

        - If `command` is provided, runs that exact command.
        - Otherwise, runs the discovered commands from analysis.lint_commands sequentially.
        - Returns combined outputs annotated with exit codes.
        """
        actual_config = config if config is not None else load_config()
        default_timeout = get_timeout_setting(actual_config, "default_shell_timeout", 60)
        cmds: list[str] = []
        if command:
            cmds = [str(command)]
        else:
            if analysis and analysis.get("lint_commands"):
                try:
                    cmds = [str(c) for c in analysis.get("lint_commands", [])]
                except Exception:
                    cmds = []
        if not cmds:
            return "NO_LINT_COMMANDS"

        outputs: list[str] = []
        for c in cmds:
            if docker and docker.get("container_id"):
                container_id = docker["container_id"]
                temp_config = actual_config
                workdir = docker.get("workdir", temp_config.docker.get("workspace_dir", "/workspace"))
                exec_cmd = f"docker exec -w {workdir} {container_id} sh -lc \"{c}\""
                code, out, err = _run(exec_cmd, cwd=str(repo_dir), timeout=timeout or default_timeout)
                outputs.append(f"$ {c}\n[exit {code}]\n{out or err}")
            else:
                code, out, err = _run(c, cwd=str(repo_dir), timeout=timeout or default_timeout)
                outputs.append(f"$ {c}\n[exit {code}]\n{out or err}")
        return "\n\n".join(outputs)

    return lint


def make_finalize_tool():
    @tool("finalize", return_direct=True)
    def finalize(commit_message: str, done: bool = True) -> str:
        """Call this when all necessary changes are complete to signal completion.
        
        IMPORTANT: If finalize is rejected, carefully read the rejection reason:
        - If "TODO comments found" → Go back and implement the actual functionality instead of placeholders
        - If "not implemented errors" → Replace throw/error statements with working code  
        - If "plan has incomplete steps" → Complete or appropriately mark remaining plan steps
        - If "core implementation steps marked stuck" → Implement those steps instead of marking stuck
        
        Do NOT repeatedly call finalize with the same issues. Address the root cause first."""
        return commit_message if done else commit_message

    return finalize


def _notes_path(repo_dir: Path, artifacts_dir: Path | None = None) -> Path:
    if artifacts_dir is not None:
        return artifacts_dir / ".devtwin_notes.jsonl"
    return repo_dir / ".devtwin_notes.jsonl"


def make_plan_read_tool(artifacts_dir: Path | None = None):
    @tool("plan_read", return_direct=False)
    def plan_read() -> str:
        """Read the current plan JSON from artifacts/plan.json and return its text.

        If the file does not exist yet, returns "NO_PLAN".
        """
        if artifacts_dir is None:
            return "NO_PLAN"
        path = artifacts_dir / "plan.json"
        try:
            if not path.exists():
                return "NO_PLAN"
            return path.read_text(encoding="utf-8")
        except Exception as e:
            return f"ERROR: {e}"

    return plan_read


def make_plan_update_tool(artifacts_dir: Path | None = None):
    @tool("plan_update", return_direct=False)
    def plan_update(
        steps: Optional[List[Dict]] = None,
        mark_completed: Optional[List[str]] = None,
        mark_in_progress: Optional[str] = None,
        mark_stuck: Optional[List[str]] = None
    ) -> str:
        """Create or update the plan in artifacts/plan.json.

        Args:
        - steps: list of step dicts with 'id', 'description', 'status' (pending/in_progress/completed/stuck)
        - mark_completed: list of step IDs to mark as completed (MUST be a list, e.g., ['step_id'] for single steps)
        - mark_in_progress: single step ID to mark as in_progress
        - mark_stuck: list of step IDs to mark as stuck when they can't be completed (e.g., due to complex test setup issues)
        
        Examples:
        - plan_update(mark_completed=['analyze_repo'])  # Single step  
        - plan_update(mark_completed=['step1', 'step2'])  # Multiple steps
        - plan_update(mark_in_progress='implement_solution')  # Set active step
        
        **Stuck Status (LAST RESORT ONLY):**
        - plan_update(mark_stuck=['setup_jest_config'])  # ✅ VALID: test configuration issue
        - plan_update(mark_stuck=['fix_docker_build'])   # ✅ VALID: build environment problem
        - plan_update(mark_stuck=['implement_dashboard']) # ❌ INVALID: core implementation work
        - plan_update(mark_stuck=['add_user_auth'])      # ❌ INVALID: feature development
        
        Use 'stuck' ONLY when blocked by external tooling/configuration factors beyond your control.
        NEVER use for core implementation, features, or business logic.
        
        Returns a short summary string.
        """
        if artifacts_dir is None:
            return "NO_ARTIFACTS_DIR"
        path = artifacts_dir / "plan.json"
        try:
            data = {}
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    data = {}
            
            # If new steps provided, replace the plan while preserving status rules
            if steps is not None:
                # Build lookup of existing steps by id (stringified)
                existing_steps_list = (data.get("steps") or []) if isinstance(data, dict) else []
                existing_by_id: dict[str, dict] = {}
                try:
                    for _s in existing_steps_list:
                        sid = str((_s or {}).get("id"))
                        if sid:
                            existing_by_id[sid] = _s
                except Exception:
                    existing_by_id = {}

                merged_steps: list[dict] = []
                for s in steps:
                    s = dict(s or {})
                    sid = str(s.get("id")) if s.get("id") is not None else ""
                    # If status not provided:
                    # - for an existing step id: keep current status
                    # - for a new step id: set to "pending"
                    if not (isinstance(s.get("status"), str) and s.get("status")):
                        if sid and sid in existing_by_id:
                            cur_status = existing_by_id[sid].get("status")
                            if isinstance(cur_status, str) and cur_status:
                                s["status"] = cur_status
                            else:
                                s["status"] = "pending"
                        else:
                            s["status"] = "pending"
                    merged_steps.append(s)

                data["steps"] = merged_steps
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                return f"PLAN_CREATED with {len(steps)} steps"
            
            # Otherwise update existing plan
            current_steps = data.get("steps") or []
            updated = 0
            
            # Mark completed steps
            if mark_completed:
                completed_set = set(str(sid) for sid in mark_completed)
                for s in current_steps:
                    if str(s.get("id")) in completed_set:
                        s["status"] = "completed"
                        updated += 1
            
            # Mark stuck steps
            if mark_stuck:
                stuck_set = set(str(sid) for sid in mark_stuck)
                for s in current_steps:
                    if str(s.get("id")) in stuck_set:
                        s["status"] = "stuck"
                        updated += 1
            
            # Mark in-progress step (and clear others)
            if mark_in_progress:
                for s in current_steps:
                    if str(s.get("id")) == str(mark_in_progress):
                        s["status"] = "in_progress"
                        updated += 1
                    elif s.get("status") == "in_progress":
                        s["status"] = "pending"
            
            data["steps"] = current_steps
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return f"PLAN_UPDATED {updated} step(s)"
        except Exception as e:
            return f"ERROR: {e}"

    return plan_update


def make_replace_tool(repo_dir: Path):
    @tool("replace_in_file", return_direct=False)
    def replace_in_file(path: str, pattern: str, replacement: str, flags: str = "", count: int = 1) -> str:
        """Regex-based, targeted edit to a UTF-8 text file relative to the repository root.

        Args:
        - path: file path relative to repo root
        - pattern: Python regex pattern
        - replacement: replacement string (supports backrefs like \1)
        - flags: optional letters combining [i]gnorecase, [m]ultiline, [s]dotall
        - count: maximum number of replacements to perform (default 1)

        Returns: A short diff-like summary with number of replacements.
        """
        file_path = _abs(repo_dir, str(path))
        try:
            text = _read(file_path)
        except FileNotFoundError:
            return f"NOT_FOUND: {path}"
        except Exception as e:
            return f"ERROR: {e}"

        re_flags = 0
        if flags:
            fl = flags.lower()
            if "i" in fl:
                re_flags |= _re.IGNORECASE
            if "m" in fl:
                re_flags |= _re.MULTILINE
            if "s" in fl:
                re_flags |= _re.DOTALL

        try:
            new_text, nrepl = _re.subn(pattern, replacement, text, count=count, flags=re_flags)
        except Exception as e:
            return f"ERROR: bad regex or replacement: {e}"

        if nrepl == 0:
            return "NO_MATCHES"
        try:
            _write(file_path, new_text)
        except Exception as e:
            return f"ERROR: could not write file: {e}"
        return f"REPLACED {nrepl} occurrence(s) in {path}"

    return replace_in_file


def make_replace_region_tool(repo_dir: Path):
    @tool("replace_region", return_direct=False)
    def replace_region(
        path: str,
        start_pattern: str,
        end_pattern: str,
        replacement: str,
        flags: str = "s",
        include_markers: bool = True,
    ) -> str:
        """Replace the first region between start_pattern and end_pattern with replacement.

        - Patterns are regex; by default DOTALL is enabled via flags='s' to span newlines.
        - If include_markers is True (default), the matched markers are replaced as well.
          If False, only the inner span is replaced, preserving the markers.
        - Returns a short summary with byte counts.
        """
        file_path = _abs(repo_dir, str(path))
        try:
            text = _read(file_path)
        except FileNotFoundError:
            return f"NOT_FOUND: {path}"
        except Exception as e:
            return f"ERROR: {e}"

        re_flags = 0
        if flags:
            fl = flags.lower()
            if "i" in fl:
                re_flags |= _re.IGNORECASE
            if "m" in fl:
                re_flags |= _re.MULTILINE
            if "s" in fl:
                re_flags |= _re.DOTALL

        try:
            sm = _re.search(start_pattern, text, flags=re_flags)
            if not sm:
                return "NO_START_MATCH"
            em = _re.search(end_pattern, text[sm.end():], flags=re_flags)
            if not em:
                return "NO_END_MATCH"
            start_idx = sm.start() if include_markers else sm.end()
            end_idx = sm.end() + (em.end() if include_markers else em.start())
            new_text = text[:start_idx] + replacement + text[end_idx:]
        except Exception as e:
            return f"ERROR: region replace failed: {e}"

        try:
            _write(file_path, new_text)
        except Exception as e:
            return f"ERROR: could not write file: {e}"
        return f"REPLACED REGION in {path}"

    return replace_region


def make_note_write_tool(repo_dir: Path, artifacts_dir: Path | None = None):
    @tool("note_write", return_direct=False)
    def note_write(topic: str, content: str) -> str:
        """Append a developer note with a topic and free-form content to the shared notes log."""
        entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "topic": str(topic),
            "content": str(content),
        }
        path = _notes_path(repo_dir, artifacts_dir)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            return f"NOTE_ADDED: {topic}"
        except Exception as e:
            return f"ERROR: could not write note: {e}"

    return note_write


def make_notes_read_tool(repo_dir: Path, artifacts_dir: Path | None = None):
    @tool("notes_read", return_direct=False)
    def notes_read(topic: Optional[str] = None, limit: int = 20) -> str:
        """Read recent notes; optionally filter by topic. Returns up to `limit` most recent entries."""
        path = _notes_path(repo_dir, artifacts_dir)
        if not path.exists():
            return "NO_NOTES"
        lines: List[str] = []
        try:
            with path.open("r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            return f"ERROR: could not read notes: {e}"
        entries: List[str] = []
        for line in reversed(lines):
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if topic and str(obj.get("topic")) != str(topic):
                continue
            entries.append(f"[{obj.get('ts')}] {obj.get('topic')}: {obj.get('content')}")
            if len(entries) >= max(1, int(limit)):
                break
        return "\n".join(entries)

    return notes_read


