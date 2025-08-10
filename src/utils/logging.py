from __future__ import annotations

from typing import Optional
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn


console = Console()


class LiveStatus:
    def __init__(self, artifacts_dir: Optional[Path] = None) -> None:
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.fields[phase]}: {task.description}"),
            expand=True,
            transient=True,
        )
        self.task_id = None
        self.artifacts_dir = artifacts_dir

    def __enter__(self) -> "LiveStatus":
        self.progress.start()
        self.task_id = self.progress.add_task("Starting Developer Twin...", total=None, phase="init")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if self.task_id is not None:
                self.progress.remove_task(self.task_id)
        finally:
            self.progress.stop()

    def update(self, message: str) -> None:
        if self.task_id is not None:
            # Expect message like "[phase] detail"; default to phase=run
            phase = "run"
            detail = message
            if message.startswith("[") and "]" in message:
                try:
                    phase = message[1 : message.index("]")]
                    detail = message[message.index("]") + 1 :].strip()
                except Exception:
                    pass
            # Truncate very long details to keep UI clean
            if len(detail) > 160:
                detail = detail[:157] + "..."
            self.progress.update(self.task_id, description=detail, phase=phase)
        else:
            console.log(message)

        # Persist status immediately to artifacts
        if self.artifacts_dir:
            try:
                log_path = self.artifacts_dir / "status.jsonl"
                log_path.parent.mkdir(parents=True, exist_ok=True)
                ts = datetime.utcnow().isoformat() + "Z"
                with log_path.open("a", encoding="utf-8") as f:
                    f.write(f"{ {'ts': ts, 'message': message} }\n")
            except Exception:
                pass


def log_panel(title: str, body: str) -> None:
    console.print(Panel.fit(body, title=title))


def write_status_line(artifacts_dir: Path, message: str) -> None:
    try:
        log_path = artifacts_dir / "status.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().isoformat() + "Z"
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"{ {'ts': ts, 'message': message} }\n")
        # Mirror to console immediately for live visibility
        console.log(message)
    except Exception:
        pass

