"""Message and history utilities for LLM interactions."""

from __future__ import annotations

from pathlib import Path
from typing import Any, List

from langchain_core.messages import AIMessage, HumanMessage


def initialize_messages(
    *,
    system_prompt: str,
    user_input: str,
    initial_messages: List | None,
    extra_user_message: str | None,
) -> List:
    """Initialize the message history for the conversation."""
    if initial_messages is not None and len(initial_messages) > 0:
        msgs = list(initial_messages)
        if extra_user_message:
            msgs.append(HumanMessage(content=extra_user_message))
        return msgs

    # Collapse system into first human turn for provider compatibility
    combined = f"<system>\n{system_prompt}\n</system>\n{user_input}"
    return [HumanMessage(content=combined)]


def trim_messages(
    msgs: List,
    *,
    keep_last_messages: int,
    max_history_chars: int,
) -> List:
    """Trim message history to stay within limits."""
    if not msgs:
        return msgs

    def content_length(m: Any) -> int:
        try:
            return len(getattr(m, "content", "") or "")
        except Exception:
            return 0

    # Handle unlimited messages (-1) or limited messages
    if keep_last_messages == -1:
        # Keep all messages
        kept = msgs[:]
    else:
        # Keep first message and last N-1 messages
        kept = [msgs[0]]
        tail = msgs[1:]
        if len(tail) > (keep_last_messages - 1):
            tail = tail[-(keep_last_messages - 1) :]
        kept.extend(tail)
    
    # Remove complete messages if total exceeds character limit
    # Always keep the first message (system + initial user) and at least one other message
    total = sum(content_length(m) for m in kept)
    while total > max_history_chars and len(kept) > 2:
        # Remove the second message (oldest after system message)
        dropped = kept.pop(1)
        total -= content_length(dropped)
        
    return kept


def clip_text(text: str, limit: int) -> str:
    """Clip text to a maximum length with truncation indicator."""
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "\n...[truncated]"


def coerce_text(content: Any) -> str:
    """Convert provider-specific content structures to a plain string safely."""
    try:
        if isinstance(content, str):
            return content
            
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                try:
                    if isinstance(item, dict):
                        # Common fields: text, value
                        val = item.get("text") or item.get("value") or ""
                        parts.append(str(val))
                    else:
                        parts.append(str(item))
                except Exception:
                    continue
            return "".join(parts)
            
        if isinstance(content, dict):
            if "text" in content:
                return str(content.get("text"))
            return str(content)
            
        return str(content)
    except Exception:
        return ""


def get_tool_calls(ai: AIMessage) -> List:
    """Extract tool calls from an AI message."""
    try:
        return getattr(ai, "tool_calls", None) or []
    except Exception:
        return []


def record_assistant_message(
    *,
    ai: AIMessage,
    tool_calls: List,
    artifacts,
    on_assistant,
    assistant_texts: List[str],
    step_index: int | None = None,
) -> None:
    """Record an assistant message to artifacts and callback."""
    try:
        raw_content = getattr(ai, "content", "")
        content_text = coerce_text(raw_content)
        
        if (content_text or "").strip():
            assistant_texts.append(content_text)
            
            event_obj = {
                "type": "assistant",
                "content": content_text,
                "has_tool_calls": bool(tool_calls),
            }
            
            if step_index is not None:
                event_obj["step"] = step_index
                
            artifacts.append_event(event_obj)
            
            if on_assistant:
                try:
                    on_assistant(content_text)
                except Exception:
                    pass
    except Exception:
        pass


def remove_last_plan_message(msgs: List) -> List:
    """Remove the most recent injected transient HumanMessage (<plan> or <turns>)."""
    try:
        for i in range(len(msgs) - 1, -1, -1):
            m = msgs[i]
            if isinstance(m, HumanMessage):
                content = getattr(m, "content", None)
                if isinstance(content, str):
                    c = content.strip()
                    if c.startswith("<plan>") or c.startswith("<turns>"):
                        return msgs[:i] + msgs[i + 1 :]
    except Exception:
        pass
    return msgs


def read_plan_text(artifacts_dir: str | Path | None) -> str | None:
    """Read plan.json text if present, else None."""
    try:
        if not artifacts_dir:
            return None
        from pathlib import Path
        path = Path(artifacts_dir) / "plan.json"
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")
    except Exception:
        return None
