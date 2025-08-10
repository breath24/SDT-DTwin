from __future__ import annotations

from typing import Any, Callable, Dict, Optional


def make_live_progress(
    agent_label: str, 
    live_update: Optional[Callable[[str], None]], 
    max_steps: int
) -> Dict[str, Any]:
    """Create standardized live progress callbacks for agents.

    Returns a dict with keys: on_assistant, on_tool_start, on_tool_end, on_step.
    """
    loop_progress: Dict[str, int] = {"cur": 0, "total": max(1, int(max_steps))}

    def _prefix(msg: str) -> str:
        try:
            return f"[{agent_label} {loop_progress['cur']}/{loop_progress['total']}] {msg}"
        except Exception:
            return f"[{agent_label}] {msg}"

    def on_assistant(text: str) -> None:
        if not live_update:
            return
        try:
            preview = (text or "").strip()
            if len(preview) > 180:
                preview = preview[:177] + "..."
            live_update(_prefix(preview))
        except Exception:
            pass

    def on_tool_start(name: str, args: Any) -> None:
        if not live_update:
            return
        try:
            live_update(_prefix(f"{name} {args}"))
        except Exception:
            pass

    def on_tool_end(name: str, res: Any) -> None:
        if not live_update:
            return
        try:
            preview = str(res)
            if len(preview) > 240:
                preview = preview[:237] + "..."
            live_update(_prefix(f"{name} -> {preview}"))
        except Exception:
            pass

    def on_step(cur: int, total: int) -> None:
        try:
            loop_progress.update({"cur": int(cur), "total": int(total)})
        except Exception:
            pass

    return {
        "on_assistant": on_assistant,
        "on_tool_start": on_tool_start,
        "on_tool_end": on_tool_end,
        "on_step": on_step,
    }


