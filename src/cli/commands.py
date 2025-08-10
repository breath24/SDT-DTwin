"""CLI utility functions for dev-twin."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Tuple


def _parse_branch_name(issue_number: int, title: str) -> str:
    """Generate a unique branch name for a GitHub issue."""
    slug = "-".join(title.lower().split())[:40]
    unique = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    return f"dev-twin/issue-{issue_number}-{slug}-{unique}"


def _project_root() -> Path:
    """Get the project root directory (parent of src/)."""
    # src/cli/ is two levels below project root
    return Path(__file__).resolve().parents[2]


def _read_issue_file(issue_path: Path) -> Tuple[str, str]:
    """Read issue title and body from a markdown file."""
    text = issue_path.read_text(encoding="utf-8") if issue_path.exists() else ""
    lines = [ln.strip() for ln in text.splitlines()]
    title = "Demo Issue"
    body_lines: list[str] = []
    for i, ln in enumerate(lines):
        if ln:
            title = ln.lstrip("# ").strip()
            body_lines = lines[i + 1 :]
            break
    body = "\n".join(body_lines).strip()
    return title, body


