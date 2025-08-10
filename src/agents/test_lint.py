from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from ..tools.lc_tools import (
    make_shell_tool,
    make_note_write_tool,
)
from ..utils.events import write_note, parse_exit_code_from_shell_result
from ..config_loader import load_config


def _discover_lint_commands(repo_dir: Path) -> List[str]:
    """Heuristic discovery of lint/static-check commands based on config presence.

    Language-agnostic: we look for common config files or package scripts and assemble
    commands accordingly. This is intentionally conservative and safe.
    """
    cmds: List[str] = []
    # Node.js / JS/TS
    pkg = repo_dir / "package.json"
    try:
        if pkg.exists():
            import json as _json
            data = _json.loads(pkg.read_text(encoding="utf-8"))
            scripts = (data.get("scripts") or {})
            if "lint" in scripts:
                cmds.append("npm run lint")
            else:
                # Config-based checks
                if (repo_dir / ".eslintrc").exists() or (repo_dir / ".eslintrc.js").exists() or (repo_dir / ".eslintrc.json").exists():
                    cmds.append("npx eslint . --max-warnings=0")
    except Exception:
        pass

    # Python
    if (repo_dir / "pyproject.toml").exists() or (repo_dir / "requirements.txt").exists():
        # Ruff
        pyproject = repo_dir / "pyproject.toml"
        pyproject_text = ""
        try:
            if pyproject.exists():
                pyproject_text = pyproject.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            pyproject_text = ""
        if (repo_dir / "ruff.toml").exists() or ("[tool.ruff]" in pyproject_text):
            cmds.append("python -m ruff check . --format=json")
        # Pyflakes as fallback if available (will just no-op if not installed)
        cmds.append("python -m pyflakes .")

    # Add more ecosystems by config presence (Go, Rust, etc.)—safe minimal checks
    if (repo_dir / "go.mod").exists():
        cmds.append("go vet ./...")
    if (repo_dir / "Cargo.toml").exists():
        cmds.append("cargo check")

    return cmds


def test_lint_node(state: dict) -> dict:
    repo_dir: Path = state["repo_dir"]
    artifacts_dir: Path = state.get("artifacts_dir", repo_dir.parent / "artifacts")

    # Build tools locally (no LLM involved here)
    config = load_config(config_file=state.get("config_file"), overrides=state.get("config_overrides"))
    shell = make_shell_tool(repo_dir, state.get("docker"), config)

    # Run tests (prefer benchmark-scoped tests if provided)
    analysis = state.get("analysis", {})
    bench = state.get("bench", {}) or {}
    bench_tests: List[str] = bench.get("test_files", []) or []
    bench_timeout: int | None = bench.get("test_timeout") if isinstance(bench.get("test_timeout"), int) else None
    test_cmds: List[str] = []
    if bench_tests:
        # Focus on only the relevant tests for this benchmark case
        joined = " ".join(bench_tests)
        test_cmds = [f"python -m pytest -q {joined}"]
    else:
        test_cmds = analysis.get("test_commands") or []
        # Heuristic if missing
        if not test_cmds:
            if (repo_dir / "package.json").exists():
                test_cmds = ["npm test -s"]
            elif (repo_dir / "pyproject.toml").exists() or (repo_dir / "requirements.txt").exists():
                test_cmds = ["python -m pytest -q"]

    last_test: Dict[str, Any] = {}
    for cmd in test_cmds:
        timeout_val = bench_timeout or 180
        res = shell.invoke({"command": cmd, "timeout": timeout_val})
        # Summarize
        try:
            # Append an event manually is already done by tool loop in LLM mode; here we parse inline

            code = parse_exit_code_from_shell_result(res)
            ok = (code == 0)
            # Persist full output for the coder to read later
            details_path: str | None = None
            try:
                artifacts_dir.mkdir(parents=True, exist_ok=True)
                path = artifacts_dir / "last_test_output.txt"
                path.write_text(str(res), encoding="utf-8")
                details_path = str(path)
            except Exception:
                details_path = None

            # Heuristic: try to extract the first failing nodeid from pytest output
            first_failed: str | None = None
            try:
                import re as _re
                text = str(res)
                m = _re.search(r"^FAILED\s+([\w\./\\:-]+)", text, flags=_re.MULTILINE)
                if m:
                    first_failed = m.group(1)
            except Exception:
                first_failed = None

            last_test = {"command": cmd, "exit": code, "ok": ok, "preview": str(res)[:240], "details_path": details_path}
            if first_failed:
                last_test["first_failed_nodeid"] = first_failed
        except Exception:
            last_test = {"command": cmd, "exit": None, "ok": None, "preview": str(res)[:240]}
        # If any test command passes fully, break
        if last_test.get("ok") is True:
            break

    state["last_test"] = last_test
    # Mark success gate only on tests; plan completeness enforced in graph
    try:
        write_note(artifacts_dir, "test", f"{last_test.get('command')} -> ok={last_test.get('ok')} exit={last_test.get('exit')}")
    except Exception:
        pass

    # Run lints (best-effort, non-fatal)
    lint_cmds = analysis.get("lint_commands") or _discover_lint_commands(repo_dir)
    state.setdefault("analysis", {})["lint_commands"] = lint_cmds
    last_lints: List[Dict[str, Any]] = []
    for cmd in lint_cmds:
        res = shell.invoke({"command": cmd, "timeout": 120})
        try:
            # Store small preview for coder
            last_lints.append({"command": cmd, "preview": str(res)[:400]})
        except Exception:
            last_lints.append({"command": cmd, "preview": "(unavailable)"})
    if last_lints:
        state["last_lint"] = last_lints
        try:
            write_note(artifacts_dir, "lint", json.dumps(last_lints)[:400])
        except Exception:
            pass

    # Reflect current plan completeness into state (for graph decisions)
    try:
        import json as _json
        plan_path = artifacts_dir / "plan.json"
        if plan_path.exists():
            plan_obj = _json.loads(plan_path.read_text(encoding="utf-8"))
            state["plan"] = plan_obj
    except Exception:
        pass

    # If tests passed and plan is complete, mark iteration done so summary reflects success
    try:
        steps = (state.get("plan") or {}).get("steps") or []
        all_complete = True if not steps else all(bool(s.get("completed")) for s in steps)
        if (last_test.get("ok") is True or last_test == {}) and all_complete:
            prev_iter = state.get("iteration") or {}
            commit_message = prev_iter.get("commit_message") or "All tests passed; plan complete."
            state["iteration"] = {
                "actions": prev_iter.get("actions", []),
                "commit_message": commit_message,
                "done": True,
            }
    except Exception:
        pass
    return state


