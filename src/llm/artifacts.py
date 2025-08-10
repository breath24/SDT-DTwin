"""Artifacts and events manager for LLM tool loops."""

from __future__ import annotations

import json as _json
from datetime import datetime as _dt
from pathlib import Path
from typing import Any, Dict, List


class ArtifactsManager:
    """Manage events.jsonl, notes jsonl and notes.md alongside an optional sink list.

    This centralizes all filesystem side effects and keeps the loop code readable.
    """

    def __init__(
        self,
        *,
        event_sink: List[Dict[str, Any]] | None,
        artifacts_dir: str | Path | None,
        note_tag: str | None,
    ) -> None:
        self._event_sink = event_sink
        self._note_tag = note_tag

        self._events_path: Path | None = None
        self._notes_path: Path | None = None
        self._notes_md_path: Path | None = None

        if artifacts_dir is not None:
            base = Path(artifacts_dir)
            self._events_path = base / "events.jsonl"
            self._notes_path = base / ".devtwin_notes.jsonl"
            self._notes_md_path = base / "notes.md"

    def loop_start(self) -> None:
        """Record the start of a loop."""
        try:
            if self._note_tag:
                self.append_note("loop_start", f"{self._note_tag} started")
        except Exception:
            pass

    def append_event(self, ev: Dict[str, Any]) -> None:
        """Append an event to both in-memory sink and persistent file."""
        # in-memory sink
        try:
            if self._event_sink is not None:
                self._event_sink.append(ev)
        except Exception:
            pass

        # persistent file
        try:
            if self._events_path is not None:
                self._events_path.parent.mkdir(parents=True, exist_ok=True)
                with self._events_path.open("a", encoding="utf-8") as f:
                    f.write(_json.dumps(ev, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def append_note(self, topic: str, content: str) -> None:
        """Append a note and regenerate notes.md."""
        if self._notes_path is None:
            return
            
        try:
            entry = {
                "ts": _dt.utcnow().isoformat() + "Z", 
                "topic": topic, 
                "content": content
            }
            
            self._notes_path.parent.mkdir(parents=True, exist_ok=True)
            with self._notes_path.open("a", encoding="utf-8") as f:
                f.write(_json.dumps(entry, ensure_ascii=False) + "\n")

            # regenerate notes.md
            if self._notes_md_path is not None:
                self._regenerate_notes_md()
        except Exception:
            pass

    def _regenerate_notes_md(self) -> None:
        """Regenerate the notes.md file from the JSONL."""
        lines_md: List[str] = []
        
        try:
            for raw in self._notes_path.read_text(encoding="utf-8").splitlines():
                try:
                    obj = _json.loads(raw)
                    lines_md.append(
                        f"- [{obj.get('ts')}] **{obj.get('topic')}**: {obj.get('content')}"
                    )
                except Exception:
                    continue
        except Exception:
            pass
            
        try:
            with self._notes_md_path.open("w", encoding="utf-8") as fmd:
                fmd.write("\n".join(lines_md) or "(no notes)")
        except Exception:
            pass

    def note_shell_exit(self, command: str, result_text: str) -> None:
        """Note shell command exit codes for tracking."""
        try:
            # parse exit code pattern [exit N]
            idx = result_text.find("[exit ")
            if idx == -1:
                return
            end = result_text.find("]", idx)
            if end == -1:
                return
            code_str = result_text[idx + 6 : end].strip()
            code_val = int(code_str)
            
            if code_val != 0:
                self.append_note("shell_error", f"{command} -> exit {code_val}")
            else:
                if "npm install" in command:
                    self.append_note("shell_ok", "npm install -> exit 0")
        except Exception:
            pass

    def maybe_note_read_not_found(self, tool_name: str, result_text: str) -> None:
        """Note file not found errors."""
        try:
            if tool_name == "read_file" and result_text.startswith("NOT_FOUND:"):
                self.append_note("read_not_found", result_text)
        except Exception:
            pass

    def maybe_note_finalize(self, tool_name: str, args: Dict[str, Any] | None) -> None:
        """Note finalize attempts."""
        try:
            if tool_name == "finalize" and isinstance(args, dict):
                cm = args.get("commit_message")
                if isinstance(cm, str) and cm:
                    self.append_note("finalize", cm)
        except Exception:
            pass

    # Accessors
    @property
    def events_path(self) -> Path | None:
        return self._events_path

    @property
    def notes_path(self) -> Path | None:
        return self._notes_path

    @property
    def notes_md_path(self) -> Path | None:
        return self._notes_md_path
