"""Main tool execution loop for LLM interactions."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from .artifacts import ArtifactsManager
from .messages import (
    initialize_messages,
    trim_messages,
    clip_text,
    get_tool_calls,
    record_assistant_message,
    remove_last_plan_message,
    read_plan_text,
)
from .validation import validate_finalize_args


def invoke_tool_safely(tool, args: Dict[str, Any]) -> Tuple[str, Any]:
    """Safely invoke a tool with error handling."""
    try:
        result = tool.invoke(args)
        try:
            return (str(result), result)
        except Exception:
            return ("(non-text result)", result)
    except Exception as e:
        return (f"Tool error: {e}", None)


def run_tool_loop(
    llm: BaseChatModel,
    tools: List,
    system_prompt: str,
    user_input: str,
    max_steps: int = 8,
    stop_on_finalize: bool = False,
    on_tool_start=None,
    on_tool_end=None,
    on_assistant=None,
    on_step=None,
    event_sink: List | None = None,
    artifacts_dir: str | Path | None = None,
    note_tag: str | None = None,
    *,
    initial_messages: List | None = None,
    extra_user_message: str | None = None,
    max_tool_result_chars: int = 4000,
    max_history_chars: int = 100000,
    keep_last_messages: int = 40,
    check_plan_completion: bool = True,
) -> Dict[str, Any]:
    """
    Run the main tool execution loop.
    
    This is the core loop that handles LLM interactions, tool calls,
    and plan management.
    """
    llm_with_tools = llm.bind_tools(tools)

    # Initialize helpers and state
    artifacts = ArtifactsManager(
        event_sink=event_sink, 
        artifacts_dir=artifacts_dir, 
        note_tag=note_tag
    )
    artifacts.loop_start()

    messages = initialize_messages(
        system_prompt=system_prompt,
        user_input=user_input,
        initial_messages=initial_messages,
        extra_user_message=extra_user_message,
    )
    
    finalize_args = None
    last_ai: AIMessage | None = None
    name_to_tool = {t.name: t for t in tools}
    assistant_texts: List[str] = []

    for step_index in range(max_steps):
        # Notify caller about step progression
        if on_step:
            try:
                on_step(step_index + 1, max_steps)
            except Exception:
                pass

        # Inject the latest plan snapshot and turn information
        _inject_context_messages(messages, artifacts_dir, step_index, max_steps, artifacts)

        # Invoke LLM with error handling
        try:
            ai = llm_with_tools.invoke(messages)
        except Exception as e:
            err_text = f"LLM error: {e}"
            artifacts.append_event({"type": "error", "where": "invoke", "message": err_text})
            # Feed back a minimal assistant message so the loop can continue
            ai = AIMessage(content=err_text)

        last_ai = ai
        messages.append(ai)

        tool_calls = get_tool_calls(ai)
        record_assistant_message(
            ai=ai,
            tool_calls=tool_calls,
            artifacts=artifacts,
            on_assistant=on_assistant,
            assistant_texts=assistant_texts,
            step_index=step_index + 1,
        )

        if not tool_calls:
            # Handle empty response or text-only turn
            content = getattr(ai, "content", "") or ""
            if content.strip():
                continue

            # Empty response: nudge if plan is incomplete
            if check_plan_completion and artifacts_dir:
                from .validation import check_plan_incomplete
                if check_plan_incomplete(artifacts_dir):
                    continuation_msg = HumanMessage(
                        content=(
                            "Your plan is not yet complete. Please continue with the remaining steps and call "
                            "finalize() when all work is done."
                        )
                    )
                    messages.append(continuation_msg)
                    messages = trim_messages(
                        messages,
                        keep_last_messages=keep_last_messages,
                        max_history_chars=max_history_chars,
                    )
                    continue
            break

        # Process tool calls
        for call in tool_calls:
            tool_name = call.get("name")
            args = call.get("args", {}) or {}
            tool_call_id = call.get("id")

            if tool_name == "finalize":
                finalize_args = _handle_finalize_call(
                    args, artifacts_dir, check_plan_completion, 
                    artifacts, messages, tool_call_id,
                    keep_last_messages, max_history_chars, stop_on_finalize,
                    last_ai, assistant_texts, event_sink
                )
                if stop_on_finalize and finalize_args:
                    return {
                        "ai_message": last_ai,
                        "messages": messages,
                        "finalize_args": finalize_args,
                        "events": event_sink,
                        "assistant_texts": assistant_texts,
                    }
                continue

            # Execute regular tool
            _execute_tool(
                tool_name, args, tool_call_id, name_to_tool,
                messages, artifacts, on_tool_start, on_tool_end,
                max_tool_result_chars
            )

        # Clean up injected context messages
        try:
            messages = remove_last_plan_message(messages)
            messages = remove_last_plan_message(messages)
        except Exception:
            pass

        # Trim messages after processing all tool results
        messages = trim_messages(
            messages, 
            keep_last_messages=keep_last_messages, 
            max_history_chars=max_history_chars
        )

    return {
        "ai_message": last_ai,
        "messages": messages,
        "finalize_args": finalize_args,
        "events": event_sink,
        "assistant_texts": assistant_texts,
    }


def _inject_context_messages(
    messages: List, 
    artifacts_dir: str | Path | None, 
    step_index: int, 
    max_steps: int,
    artifacts: ArtifactsManager
) -> None:
    """Inject plan and turn context as transient messages."""
    try:
        plan_text = read_plan_text(artifacts_dir)
        turns_remaining = max(0, max_steps - (step_index + 1))
        
        # Log input snapshot
        try:
            preview_msgs = []
            for m in messages[-3:]:
                try:
                    preview_msgs.append({
                        "type": m.__class__.__name__,
                        "content_preview": clip_text(getattr(m, "content", "") or "", 1000),
                    })
                except Exception:
                    continue
                    
            artifacts.append_event({
                "type": "step_input",
                "step": step_index + 1,
                "messages_preview": preview_msgs,
                "plan_text": clip_text(plan_text or "", 3000),
                "turns_remaining": turns_remaining,
                "max_steps": max_steps,
            })
        except Exception:
            pass

        if plan_text:
            messages.append(HumanMessage(content=f"<plan>\n{plan_text}\n</plan>"))
            
        # Inject turns remaining as a transient hint
        messages.append(
            HumanMessage(
                content=f"<turns>\nstep={step_index + 1}\nremaining={turns_remaining}\nmax={max_steps}\n</turns>"
            )
        )
    except Exception:
        pass


def _handle_finalize_call(
    args: Dict[str, Any],
    artifacts_dir: str | Path | None,
    check_plan_completion: bool,
    artifacts: ArtifactsManager,
    messages: List,
    tool_call_id: str,
    keep_last_messages: int,
    max_history_chars: int,
    stop_on_finalize: bool,
    last_ai: AIMessage,
    assistant_texts: List[str],
    event_sink: List | None,
) -> Optional[Dict[str, Any]]:
    """Handle finalize tool call with validation."""
    ok, reasons, incomplete_steps = validate_finalize_args(
        args=args,
        artifacts_dir=artifacts_dir,
        check_plan_completion=check_plan_completion,
    )

    if not ok:
        # Reject finalize
        preview_steps = ", ".join(str(s.get("id")) for s in incomplete_steps[:6])
        detail = f" Remaining steps: {preview_steps}" if preview_steps else ""
        
        artifacts.append_event({
            "tool": "finalize", 
            "args": args, 
            "result": f"rejected: {'; '.join(reasons)}{detail}"
        })
        
        messages.append(ToolMessage(content=str(args), tool_call_id=tool_call_id))
        
        nudge_text = (
            "Your plan is not fully complete or commit_message is missing. Please complete and mark "
            "remaining steps via plan_update, write a clear commit_message, then call finalize again."
        )
        
        if incomplete_steps:
            try:
                ids = ", ".join(str(s.get("id")) for s in incomplete_steps)
                nudge_text += f" Incomplete step ids: {ids}."
            except Exception:
                pass
                
        messages.append(HumanMessage(content=nudge_text))
        messages = trim_messages(
            messages, 
            keep_last_messages=keep_last_messages, 
            max_history_chars=max_history_chars
        )
        return None

    # Accept finalize
    messages.append(ToolMessage(content=str(args), tool_call_id=tool_call_id))
    messages = trim_messages(
        messages, 
        keep_last_messages=keep_last_messages, 
        max_history_chars=max_history_chars
    )
    
    artifacts.append_event({"tool": "finalize", "args": args, "result": "finalize"})
    artifacts.maybe_note_finalize("finalize", args)
    
    return args


def _execute_tool(
    tool_name: str,
    args: Dict[str, Any],
    tool_call_id: str,
    name_to_tool: Dict[str, Any],
    messages: List,
    artifacts: ArtifactsManager,
    on_tool_start,
    on_tool_end,
    max_tool_result_chars: int,
) -> None:
    """Execute a regular (non-finalize) tool."""
    tool = name_to_tool.get(tool_name)
    if tool is None:
        messages.append(ToolMessage(content=f"Unknown tool {tool_name}", tool_call_id=tool_call_id))
        return

    if on_tool_start:
        try:
            on_tool_start(tool_name, args)
        except Exception:
            pass

    # Execute tool safely
    res_text, raw_result = invoke_tool_safely(tool, args)
    
    # Record event
    tool_event = {"tool": tool_name, "args": args, "result": str(res_text)}
    artifacts.append_event(tool_event)

    # Clip and append tool message
    res_text = clip_text(res_text, max_tool_result_chars)
    
    # Ensure valid call_id
    if not tool_call_id:
        try:
            import uuid
            tool_call_id = f"call_{uuid.uuid4().hex}"
        except Exception:
            tool_call_id = "call_synth"
    else:
        # Re-inject function call for strict APIs
        try:
            from langchain_core.messages import AIMessage as _AIMessage
            _echo_call = {
                "name": str(tool_name),
                "args": args if isinstance(args, dict) else ({}),
                "id": str(tool_call_id),
            }
            messages.append(_AIMessage(content="", additional_kwargs={"tool_calls": [_echo_call]}))
        except Exception:
            pass
            
    messages.append(ToolMessage(content=res_text, tool_call_id=tool_call_id))

    # Auto notes
    if tool_name == "shell":
        artifacts.note_shell_exit(args.get("command", ""), str(res_text))
    artifacts.maybe_note_read_not_found(tool_name, str(res_text))

    if on_tool_end:
        try:
            preview = str(res_text)
            if len(preview) > 240:
                preview = preview[:237] + "..."
            on_tool_end(tool_name, preview)
        except Exception:
            pass
