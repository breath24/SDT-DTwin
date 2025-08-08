from __future__ import annotations

import os
from typing import Dict, Any, Union
from pathlib import Path
import json as _json

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.language_models import BaseChatModel


def make_llm(
    provider: str,
    model: str,
    api_key: str,
    base_url: str | None = None,
) -> BaseChatModel:
    """
    Create an LLM instance based on the provider and model.
    
    Args:
        provider: Provider name ("google", "openai", "anthropic", "openrouter")
        model: Model identifier (e.g., "gemini-2.0-flash", "gpt-4o", "claude-3-5-sonnet-20241022")
        api_key: API key for the provider
        base_url: Base URL for custom endpoints (mainly for OpenRouter)
    
    Returns:
        Configured LLM instance
    """
    if not api_key:
        raise ValueError(f"API key is required for provider {provider}")
    
    if provider == "google":
        return ChatGoogleGenerativeAI(model=model, api_key=api_key)
    
    elif provider == "openai":
        kwargs = {"model": model, "api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        return ChatOpenAI(**kwargs)
    
    elif provider == "anthropic":
        return ChatAnthropic(model=model, api_key=api_key)
    
    elif provider == "openrouter":
        # OpenRouter uses OpenAI-compatible API
        if base_url is None:
            base_url = "https://openrouter.ai/api/v1"
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
        )
    
    else:
        raise ValueError(f"Unknown provider: {provider}. Supported providers: google, openai, anthropic, openrouter")


def make_llm_from_settings(settings, model: str | None = None) -> BaseChatModel:
    """
    Create an LLM from settings object. Convenience function for backward compatibility.
    
    Args:
        settings: Settings object containing provider, API keys, and default model
        model: Model to use (if None, uses settings.default_model)
    
    Returns:
        Configured LLM instance
    """
    if model is None:
        model = settings.default_model
    
    api_key = settings.get_current_api_key()
    base_url = settings.base_url if settings.base_url else None
    
    return make_llm(
        provider=settings.provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
    )


def run_tool_loop(
    llm: BaseChatModel,
    tools: list,
    system_prompt: str,
    user_input: str,
    max_steps: int = 8,
    stop_on_finalize: bool = False,
    on_tool_start=None,
    on_tool_end=None,
    event_sink: list | None = None,
    artifacts_dir: str | Path | None = None,
    note_tag: str | None = None,
    *,
    initial_messages: list | None = None,
    extra_user_message: str | None = None,
    max_tool_result_chars: int = 4000,
    max_history_chars: int = 100000,
    keep_last_messages: int = 40,
):
    llm_with_tools = llm.bind_tools(tools)
    # Allow resuming a prior conversation thread to preserve context across iterations
    if initial_messages is not None and len(initial_messages) > 0:
        messages = list(initial_messages)
        if extra_user_message:
            messages.append(HumanMessage(content=extra_user_message))
    else:
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_input)]
    finalize_args = None
    last_ai: AIMessage | None = None

    name_to_tool = {t.name: t for t in tools}
    repeat_counter: dict[tuple[str, str], int] = {}
    # Group-level repetition guards (e.g., various forms of running tests)
    group_repeat_counter: dict[str, int] = {}

    events_path: Path | None = None
    notes_path: Path | None = None
    notes_md_path: Path | None = None
    if artifacts_dir is not None:
        events_path = Path(artifacts_dir) / "events.jsonl"
        notes_path = Path(artifacts_dir) / ".devtwin_notes.jsonl"
        notes_md_path = Path(artifacts_dir) / "notes.md"

    def _append_event(ev: Dict[str, Any]):
        if event_sink is not None:
            event_sink.append(ev)
        if events_path is not None:
            try:
                events_path.parent.mkdir(parents=True, exist_ok=True)
                with events_path.open("a", encoding="utf-8") as f:
                    f.write(_json.dumps(ev, ensure_ascii=False) + "\n")
            except Exception:
                pass

    def _append_note(topic: str, content: str):
        if notes_path is None:
            return
        try:
            from datetime import datetime as _dt
            entry = {"ts": _dt.utcnow().isoformat() + "Z", "topic": topic, "content": content}
            notes_path.parent.mkdir(parents=True, exist_ok=True)
            with notes_path.open("a", encoding="utf-8") as f:
                f.write(_json.dumps(entry, ensure_ascii=False) + "\n")
            # regenerate notes.md
            if notes_md_path is not None:
                lines_md = []
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

    # Write a starting note for this loop (for better traceability)
    try:
        if note_tag:
            _append_note("loop_start", f"{note_tag} started")
    except Exception:
        pass

    def _trim_messages(msgs: list):
        if not msgs:
            return msgs
        def _content_len(m):
            try:
                return len(getattr(m, "content", "") or "")
            except Exception:
                return 0
        kept = [msgs[0]]
        tail = msgs[1:]
        if len(tail) > (keep_last_messages - 1):
            tail = tail[-(keep_last_messages - 1):]
        kept.extend(tail)
        total = sum(_content_len(m) for m in kept)
        while total > max_history_chars and len(kept) > 2:
            dropped = kept.pop(1)
            total -= _content_len(dropped)
        return kept

    for _ in range(max_steps):
        ai = llm_with_tools.invoke(messages)
        last_ai = ai
        # CRITICAL: include the assistant's message (with tool_calls) in history
        # so that subsequent ToolMessage entries correctly associate via tool_call_id.
        messages.append(ai)
        messages = _trim_messages(messages)
        tool_calls = getattr(ai, "tool_calls", None) or []
        if not tool_calls:
            # no tool calls, done this step
            break
        for call in tool_calls:
            tool_name = call.get("name")
            args = call.get("args", {}) or {}
            tool_call_id = call.get("id")
            if tool_name == "finalize":
                finalize_args = args
                # still append the tool message for completeness
                messages.append(ToolMessage(content=str(args), tool_call_id=tool_call_id))
                messages = _trim_messages(messages)
                _append_event({"tool": tool_name, "args": args, "result": "finalize"})
                # Note the finalize commit message for visibility
                try:
                    cm = args.get("commit_message") if isinstance(args, dict) else None
                    if cm:
                        _append_note("finalize", cm)
                except Exception:
                    pass
                if stop_on_finalize:
                    return {
                        "ai_message": last_ai,
                        "messages": messages,
                        "finalize_args": finalize_args,
                        "events": event_sink,
                    }
                continue
            tool = name_to_tool.get(tool_name)
            if tool is None:
                messages.append(ToolMessage(content=f"Unknown tool {tool_name}", tool_call_id=tool_call_id))
                continue
            if on_tool_start:
                try:
                    on_tool_start(tool_name, args)
                except Exception:
                    pass
            # repetition guard key
            try:
                key = (tool_name, _json.dumps(args, sort_keys=True))
            except Exception:
                key = (tool_name, str(args))
            repeat_counter[key] = repeat_counter.get(key, 0) + 1

            # Invoke tool (with repeat skip for shell)
            if tool_name == "shell":
                cmd = str(args.get("command", ""))
                # Normalize common test runner variants into one group
                import re as _re
                norm_group = None
                if _re.search(r"\b(npm|pnpm|yarn)\s+test\b", cmd) or _re.search(r"\bnpx\s+jest\b", cmd) or _re.search(r"\bjest\b", cmd):
                    norm_group = "TEST_RUNNER"
                if norm_group:
                    group_repeat_counter[norm_group] = group_repeat_counter.get(norm_group, 0) + 1
                    if group_repeat_counter[norm_group] >= 3:
                        result = (
                            f"SKIPPED_REPEAT_GROUP: {norm_group} invoked {group_repeat_counter[norm_group]} times with variations. "
                            "Suppressed to avoid loops."
                        )
                        try:
                            _append_note("test_runner_suppressed", f"{cmd}")
                        except Exception:
                            pass
                    elif repeat_counter[key] >= 3:
                        result = f"SKIPPED_REPEAT: shell command repeated {repeat_counter[key]} times. Adjust your approach."
                    else:
                        result = tool.invoke(args)
                elif repeat_counter[key] >= 3:
                    result = f"SKIPPED_REPEAT: shell command repeated {repeat_counter[key]} times. Adjust your approach."
                else:
                    result = tool.invoke(args)
            else:
                result = tool.invoke(args)

            # If the same read_file call repeats, inject a guard hint in the result
            if tool_name == "read_file" and repeat_counter[key] >= 3:
                prefix = "\n\nREPEAT_GUARD: read_file called multiple times for the same path. Consider search/list_dir or write_file instead."
                try:
                    result = (result or "") + prefix
                except Exception:
                    result = str(result) + prefix
            # If the same shell command repeats, inject a guard hint in the result
            if tool_name == "shell" and repeat_counter[key] >= 2:
                hint = (
                    "\n\nREPEAT_GUARD: shell invoked with the same command multiple times. "
                    "If the command fails, adjust strategy (e.g., on Windows prefer 'python -m <module>' instead of invoking the module directly; use 'where' instead of 'which')."
                )
                try:
                    result = (result or "") + hint
                except Exception:
                    result = str(result) + hint
            # Tool may return non-string; coerce and clip
            try:
                res_text = str(result)
            except Exception:
                res_text = "(non-text result)"
            if len(res_text) > max_tool_result_chars:
                res_text = res_text[: max_tool_result_chars - 20] + "\n...[truncated]"
            messages.append(ToolMessage(content=res_text, tool_call_id=tool_call_id))
            messages = _trim_messages(messages)
            _append_event({"tool": tool_name, "args": args, "result": str(result)})
            # Auto-note on common conditions
            try:
                if tool_name == "shell":
                    text = str(result)
                    # parse exit code pattern [exit N]
                    idx = text.find("[exit ")
                    if idx != -1:
                        end = text.find("]", idx)
                        if end != -1:
                            code_str = text[idx + 6 : end].strip()
                            try:
                                code_val = int(code_str)
                                if code_val != 0:
                                    _append_note("shell_error", f"{args.get('command', '')} -> exit {code_val}")
                            except Exception:
                                pass
                if tool_name == "read_file" and str(result).startswith("NOT_FOUND:"):
                    _append_note("read_not_found", str(result))
                if tool_name == "finalize":
                    cm = args.get("commit_message") if isinstance(args, dict) else None
                    if cm:
                        _append_note("finalize", cm)
                # Encourage success/failure notes for non-zero exits and key successes
                try:
                    if tool_name == "shell":
                        if "[exit 0]" in text:
                            if "npm install" in (args.get("command", "")):
                                _append_note("shell_ok", "npm install -> exit 0")
                        elif "[exit " in text and "[exit 0]" not in text:
                            cmd = args.get("command", "")
                            _append_note("shell_error", f"{cmd} -> non-zero exit")
                except Exception:
                    pass
            except Exception:
                pass
            if on_tool_end:
                try:
                    # Truncate result for live log
                    preview = str(result)
                    if len(preview) > 240:
                        preview = preview[:237] + "..."
                    on_tool_end(tool_name, preview)
                except Exception:
                    pass

    return {"ai_message": last_ai, "messages": messages, "finalize_args": finalize_args, "events": event_sink}


