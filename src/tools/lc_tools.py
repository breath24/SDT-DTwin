from __future__ import annotations

from pathlib import Path
from typing import Optional, List, Dict, Any
import json
from datetime import datetime

from langchain_core.tools import tool

from .fs import read_file_text as _read, write_file_text as _write, list_directory as _ls, search_ripgrep as _search
from .shell import run_shell as _run


def _abs(repo_dir: Path, rel: str) -> str:
    p = repo_dir / rel
    return str(p)


def make_read_tool(repo_dir: Path):
    @tool("read_file", return_direct=False)
    def read_file(path) -> str:
        """Read a UTF-8 text file relative to the repository root."""
        try:
            return _read(_abs(repo_dir, str(path)))
        except FileNotFoundError:
            return f"NOT_FOUND: {path}"
        except Exception as e:
            return f"ERROR: {e}"

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


def make_shell_tool(repo_dir: Path, docker: Optional[Dict[str, Any]] = None):
    @tool("shell", return_direct=False)
    def shell(command: str, timeout: Optional[int] = None) -> str:
        """Run a shell command non-interactively in the repository root."""
        # Default to a hard 60s timeout to avoid hanging dev servers or long-running processes
        if timeout is None:
            timeout = 60
        if docker and docker.get("container_id"):
            container_id = docker["container_id"]
            workdir = docker.get("workdir", "/workspace")
            # Execute inside container with POSIX shell
            exec_cmd = f"docker exec -w {workdir} {container_id} sh -lc \"{command}\""
            code, out, err = _run(exec_cmd, cwd=str(repo_dir), timeout=timeout)
            return f"$ {command}\n[exit {code}]\n{out or err}"
        code, out, err = _run(command, cwd=str(repo_dir), timeout=timeout)
        return f"$ {command}\n[exit {code}]\n{out or err}"

    return shell


def make_finalize_tool():
    @tool("finalize", return_direct=True)
    def finalize(commit_message: str, done: bool = True) -> str:
        """Call this when all necessary changes are complete to signal completion."""
        return commit_message if done else commit_message

    return finalize


def _notes_path(repo_dir: Path, artifacts_dir: Path | None = None) -> Path:
    if artifacts_dir is not None:
        return artifacts_dir / ".devtwin_notes.jsonl"
    return repo_dir / ".devtwin_notes.jsonl"


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


