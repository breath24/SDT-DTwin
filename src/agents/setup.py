from __future__ import annotations

import json
from pathlib import Path

from ..llm import make_llm_from_settings, run_tool_loop
from ..tools.lc_tools import make_shell_tool, make_list_tool, make_read_tool, make_search_tool, make_note_write_tool, make_notes_read_tool, make_finalize_tool
from ..config_loader import load_config, get_agent_config, load_prompt, get_agent_history_setting
from ..utils.events import summarize_last_test_event
from ..utils.progress import make_live_progress


def setup_node(state: dict) -> dict:
    # Load configuration
    config = load_config(config_file=state.get("config_file"), overrides=state.get("config_overrides"))
    agent_config = get_agent_config(config, "setup")
    
    llm = make_llm_from_settings(state["settings"])
    repo_dir: Path = state["repo_dir"]
    analysis = state.get("analysis", {})
    transcript = state.get("transcript", [])
    live = state.get("live_update")
    events = state.get("events")

    tools = [
        make_shell_tool(repo_dir, state.get("docker"), config),
        make_list_tool(repo_dir),
        make_read_tool(repo_dir),
        make_search_tool(repo_dir),
        make_notes_read_tool(repo_dir, state.get("artifacts_dir")),
        make_note_write_tool(repo_dir, state.get("artifacts_dir")),
        make_finalize_tool(),
    ]

    context = {
        "analysis": analysis,
        "transcript_tail": transcript[-4:],
    }

    if live:
        live("[setup] Preparing environment...")

    # Progress helpers for better UI feedback
    progress = make_live_progress("setup", live, agent_config.max_steps)
    _on_assistant = progress["on_assistant"]
    _on_tool_start = progress["on_tool_start"]
    _on_tool_end = progress["on_tool_end"]
    _on_step = progress["on_step"]

    # Load prompt from file
    setup_prompt = load_prompt("setup")
    
    # Get agent-specific history settings
    max_history_chars = get_agent_history_setting(config, "setup", "max_history_chars")
    keep_last_messages = get_agent_history_setting(config, "setup", "keep_last_messages")
    max_tool_result_chars = get_agent_history_setting(config, "setup", "max_tool_result_chars")
    
    run_tool_loop(
        llm,
        tools,
        setup_prompt,
        json.dumps(context),
        max_steps=agent_config.max_steps,
        stop_on_finalize=True,
        on_tool_start=_on_tool_start,
        on_tool_end=_on_tool_end,
        on_assistant=_on_assistant,
        on_step=_on_step,
        event_sink=events,
        artifacts_dir=state.get("artifacts_dir"),
        note_tag="setup",
        max_history_chars=max_history_chars,
        keep_last_messages=keep_last_messages,
        max_tool_result_chars=max_tool_result_chars,
    )

    # Summarize the last test run (if any) for downstream nodes
    try:

        events_list = state.get("events") or []
        last_test = summarize_last_test_event(events_list)
        if last_test:
            state["last_test"] = last_test
    except Exception:
        pass

    # No special state changes; setup is best-effort. Continue to planner.
    return state


