from __future__ import annotations

import json
from pathlib import Path

import platform

from ..llm import make_llm_from_settings, run_tool_loop
from ..tools.lc_tools import (
    make_read_tool,
    make_write_tool,
    make_list_tool,
    make_search_tool,
    make_replace_tool,
    make_replace_region_tool,
    make_apply_patch_tool,
    make_lint_tool,
    make_plan_read_tool,
    make_plan_update_tool,
    make_shell_tool,
    make_finalize_tool,
    make_note_write_tool,
    make_notes_read_tool,
)
from .schemas import CodeIteration
from ..config_loader import load_config, get_agent_config, load_prompt, get_agent_history_setting
from ..utils.events import write_note, summarize_last_test_event
from ..utils.progress import make_live_progress
from ..tools import write_file_text


def coder_node(state: dict) -> dict:
    # Load configuration
    config = load_config(config_file=state.get("config_file"), overrides=state.get("config_overrides"))
    agent_config = get_agent_config(config, "coder")
    
    llm = make_llm_from_settings(state["settings"])
    repo_dir: Path = state["repo_dir"]
    plan = state["plan"]
    issue = state["issue"]
    analysis = state["analysis"]
    transcript = state.get("transcript", [])

    artifacts_dir = state.get("artifacts_dir", repo_dir.parent / "artifacts")
    tools = [
        make_read_tool(repo_dir),
        make_write_tool(repo_dir),
        make_list_tool(repo_dir),
        make_search_tool(repo_dir),
        make_replace_tool(repo_dir),
        make_replace_region_tool(repo_dir),
        make_apply_patch_tool(repo_dir),
        make_lint_tool(repo_dir, state.get("analysis"), state.get("docker"), config),
        make_plan_read_tool(state.get("artifacts_dir")),
        make_plan_update_tool(state.get("artifacts_dir")),
        make_shell_tool(repo_dir, state.get("docker"), config),
        make_notes_read_tool(repo_dir, artifacts_dir),
        make_note_write_tool(repo_dir, artifacts_dir),
        make_finalize_tool(),
    ]
    # Use tool loop so tools actually execute in multiple steps and we can detect finalize
    # Read recent notes (if present) to prime the model with context without tool calls
    notes_recent: list[str] = []
    try:
        notes_path = (state.get("artifacts_dir", repo_dir.parent / "artifacts") / ".devtwin_notes.jsonl")
        if notes_path.exists():
            lines = notes_path.read_text(encoding="utf-8").splitlines()
            for raw in reversed(lines[-50:]):
                try:
                    obj = json.loads(raw)
                    notes_recent.append(f"[{obj.get('ts')}] {obj.get('topic')}: {obj.get('content')}")
                except Exception:
                    continue
            notes_recent = list(reversed(notes_recent[-20:]))
    except Exception:
        pass
    # Embed the full plan JSON verbatim to ensure it is always visible
    plan_text_verbatim = ""
    try:
        plan_text_verbatim = json.dumps(plan, ensure_ascii=False, indent=2)
    except Exception:
        try:
            plan_text_verbatim = str(plan)
        except Exception:
            plan_text_verbatim = "{}"
    context = {
        "issue": {"title": issue.title, "body": issue.body},
        "analysis": analysis,
        "plan": plan,
        "plan_text": plan_text_verbatim,
        "transcript_tail": transcript[-4:],
        "environment": {
            "os": platform.system(),
            "platform": platform.platform(),
        },
        "notes_recent": notes_recent,
        # Provide visibility into the last test run, if any
        "last_test": state.get("last_test", {}),
        "write_policy": (
            "Always provide full relative paths with forward slashes when writing files (e.g., 'src/components/Dashboard.jsx'). "
            "Do not use bare filenames. After reading a few files, perform targeted write_file edits to implement TODOs and remove thrown errors."
        ),
    }
    live = state.get("live_update")
    events = state.get("events")
    if live:
        live("[coder] Working on implementation...")

    # Progress helpers for better UI feedback
    progress = make_live_progress("coder", live, agent_config.max_steps)
    _on_assistant = progress["on_assistant"]
    _on_tool_start = progress["on_tool_start"]
    _on_tool_end = progress["on_tool_end"]
    _on_step = progress["on_step"]
    # Resume prior conversation to prevent context reset between iterations
    # Reuse prior conversation but cap history to avoid runaway context growth
    prior_messages = state.get("coder_messages")
    if isinstance(prior_messages, list) and len(prior_messages) > 60:
        prior_messages = prior_messages[-60:]
    
    # Load prompt from file
    coder_prompt = load_prompt("coder")
    
    # Get agent-specific history settings
    max_history_chars = get_agent_history_setting(config, "coder", "max_history_chars")
    keep_last_messages = get_agent_history_setting(config, "coder", "keep_last_messages")
    max_tool_result_chars = get_agent_history_setting(config, "coder", "max_tool_result_chars")
    
    result = run_tool_loop(
        llm,
        tools,
        coder_prompt,
        json.dumps(context),
        max_steps=agent_config.max_steps,
        stop_on_finalize=True,
        on_tool_start=_on_tool_start,
        on_tool_end=_on_tool_end,
        on_assistant=_on_assistant,
        on_step=_on_step,
        event_sink=events,
        artifacts_dir=state.get("artifacts_dir"),
        initial_messages=prior_messages,
        extra_user_message=json.dumps({"continue": True, "context": context}),
        note_tag="coder",
        max_history_chars=max_history_chars,
        keep_last_messages=keep_last_messages,
        max_tool_result_chars=max_tool_result_chars,
    )
    ai = result.get("ai_message")
    text = getattr(ai, "content", None) or ""
    finalize_args = result.get("finalize_args") or {}
    done = bool(finalize_args.get("done", False))
    commit_message = finalize_args.get("commit_message", "dev-twin changes")
    # Enforce plan completeness at coder level too: if plan incomplete, override done to False
    try:
        # Reload plan from artifacts so `plan_update` tool changes reflect in state
        try:
            artifacts_dir = state.get("artifacts_dir")
            if artifacts_dir:
                plan_path = Path(artifacts_dir) / "plan.json"
                if plan_path.exists():
                    updated_plan = json.loads(plan_path.read_text(encoding="utf-8"))
                    if isinstance(updated_plan, dict):
                        state["plan"] = updated_plan
        except Exception:
            pass
        steps = (state.get("plan") or {}).get("steps") or []
        if steps and not all(bool(s.get("completed")) for s in steps):
            done = False
    except Exception:
        pass

    iteration: CodeIteration = {
        "actions": [],
        "commit_message": commit_message,
        "done": done,
    }

    # If test runner loops were suppressed or repeated without success, do NOT finalize.
    # Instead, write a note so the next iteration can adjust strategy.
    if not done:
        try:
            txt_lower = (text or "").lower()
        except Exception:
            txt_lower = ""
        if ("skipped_repeat_group" in txt_lower) or ("test_runner_suppressed" in txt_lower):
            try:

                artifacts_dir = state.get("artifacts_dir")
                if artifacts_dir:
                    write_note(artifacts_dir, "stuck", "Test runs suppressed by repetition guard; reconsider strategy or adjust commands.")
            except Exception:
                pass

    transcript.append({
        "input": context,
        "output": {
            "text": text,
            "finalize": finalize_args,
            "assistant_messages": result.get("assistant_texts", []),
        },
    })
    # Persist transcript incrementally
    try:
        artifacts_dir = state.get("artifacts_dir")
        if artifacts_dir:

            write_file_text(str(artifacts_dir / "transcript.json"), json.dumps(transcript, indent=2))
    except Exception:
        pass
    # Persist conversation messages for continuity in the next loop
    state["coder_messages"] = result.get("messages") or prior_messages
    # Summarize the last test run (if any) after coder actions
    try:

        events_list = state.get("events") or []
        artifacts_dir = state.get("artifacts_dir")
        last_test = summarize_last_test_event(events_list, artifacts_dir=artifacts_dir)
        if last_test:
            state["last_test"] = last_test
    except Exception:
        pass
    return {**state, "iteration": iteration, "transcript": transcript, "coder_messages": state["coder_messages"]}


