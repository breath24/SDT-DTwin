from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from pathlib import Path
import json as _json
from datetime import datetime as _dt


_EXIT_RE = re.compile(r"\[exit\s+(\d+)\]")


def parse_exit_code_from_shell_result(text: str) -> Optional[int]:
    if not text:
        return None
    m = _EXIT_RE.search(text)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _looks_like_test_command(cmd: str) -> bool:
    if not cmd:
        return False
    c = cmd.lower()
    return (
        "pytest" in c
        or re.search(r"\b(npm|pnpm|yarn)\s+test\b", c) is not None
        or "npx jest" in c
        or re.search(r"\bjest\b", c) is not None
    )


def summarize_last_test_event(events: List[Dict[str, Any]], artifacts_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Find the most recent shell event that looks like a test run and summarize it.

    Returns an empty dict if not found.
    """
    if not isinstance(events, list):
        return {}
    for ev in reversed(events):
        if not isinstance(ev, dict):
            continue
        if ev.get("tool") != "shell":
            continue
        args = ev.get("args") or {}
        cmd = str(args.get("command", ""))
        if not _looks_like_test_command(cmd):
            continue
        result_text = str(ev.get("result", ""))
        code = parse_exit_code_from_shell_result(result_text)
        if code is None:
            # Sometimes code is omitted; treat as unknown
            ok = None
        else:
            ok = (code == 0)
        preview = result_text[:240]
        details_path: Optional[str] = None
        if artifacts_dir is not None:
            try:
                artifacts_dir.mkdir(parents=True, exist_ok=True)
                path = artifacts_dir / "last_test_output.txt"
                path.write_text(result_text, encoding="utf-8")
                details_path = str(path)
            except Exception:
                details_path = None
        return {"command": cmd, "exit": code, "ok": ok, "preview": preview, "details_path": details_path}
    return {}


def write_note(artifacts_dir: Path | str, topic: str, content: str) -> None:
    """Append a note to artifacts/.devtwin_notes.jsonl and refresh notes.md.

    Best-effort; silently ignores IO errors.
    """
    try:
        base = Path(artifacts_dir)
        notes_path = base / ".devtwin_notes.jsonl"
        notes_md_path = base / "notes.md"
        entry = {
            "ts": _dt.utcnow().isoformat() + "Z",
            "topic": str(topic),
            "content": str(content),
        }
        notes_path.parent.mkdir(parents=True, exist_ok=True)
        with notes_path.open("a", encoding="utf-8") as f:
            f.write(_json.dumps(entry, ensure_ascii=False) + "\n")
        # Rebuild notes.md
        lines_md: list[str] = []
        try:
            for raw in notes_path.read_text(encoding="utf-8").splitlines():
                try:
                    obj = _json.loads(raw)
                    lines_md.append(f"- [{obj.get('ts')}] **{obj.get('topic')}**: {obj.get('content')}")
                except Exception:
                    continue
        except Exception:
            pass
        try:
            with notes_md_path.open("w", encoding="utf-8") as fmd:
                fmd.write("\n".join(lines_md) or "(no notes)")
        except Exception:
            pass
    except Exception:
        pass


