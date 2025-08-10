from __future__ import annotations

import json

from ..llm import make_llm_from_settings, run_tool_loop
from ..tools.lc_tools import make_list_tool, make_read_tool, make_search_tool, make_finalize_tool
from ..utils.progress import make_live_progress
from .schemas import Plan
from ..utils.json_utils import extract_first_json_object
from ..config_loader import load_config, get_agent_config, load_prompt, get_agent_history_setting
from ..tools import write_file_text


def planner_node(state: dict) -> dict:
    # Load configuration
    config = load_config(config_file=state.get("config_file"), overrides=state.get("config_overrides"))
    agent_config = get_agent_config(config, "planner")
    
    llm = make_llm_from_settings(state["settings"])
    issue = state["issue"]
    analysis = state["analysis"]
    inputs = {
        "issue": {"title": issue.title, "body": issue.body},
        "analysis": analysis,
    }
    tools = [
        make_list_tool(state["repo_dir"]),
        make_read_tool(state["repo_dir"]),
        make_search_tool(state["repo_dir"]),
        make_finalize_tool(),
    ]
    live = state.get("live_update")
    events = state.get("events")
    if live:
        live("[planner] Generating plan...")

    # Progress helpers for better UI feedback
    progress = make_live_progress("planner", live, agent_config.max_steps)
    _on_assistant = progress["on_assistant"]
    _on_tool_start = progress["on_tool_start"]
    _on_tool_end = progress["on_tool_end"]
    _on_step = progress["on_step"]
    
    # Load prompt from file
    planner_prompt = load_prompt("planner")
    
    # Get agent-specific history settings
    max_history_chars = get_agent_history_setting(config, "planner", "max_history_chars")
    keep_last_messages = get_agent_history_setting(config, "planner", "keep_last_messages")
    max_tool_result_chars = get_agent_history_setting(config, "planner", "max_tool_result_chars")
    
    result = run_tool_loop(
        llm,
        tools,
        planner_prompt,
        json.dumps(inputs),
        max_steps=agent_config.max_steps,
        stop_on_finalize=True,
        on_tool_start=_on_tool_start,
        on_tool_end=_on_tool_end,
        on_assistant=_on_assistant,
        on_step=_on_step,
        event_sink=events,
        artifacts_dir=state.get("artifacts_dir"),
        note_tag="planner",
        max_history_chars=max_history_chars,
        keep_last_messages=keep_last_messages,
        max_tool_result_chars=max_tool_result_chars,
    )
    ai = result.get("ai_message")
    text = getattr(ai, "content", None) or ""
    data = extract_first_json_object(text)
    steps = data.get("steps") or []
    # Fallback minimal plan if model returned nothing
    if not steps:
        steps = [
            {"id": "analyze-repo", "description": "Inspect repo and identify failing TODOs", "rationale": "Establish baseline"},
            {"id": "implement-stubs", "description": "Replace thrown errors/TODOs with minimal working implementations", "rationale": "Enable app/tests to run"},
            {"id": "wire-tests", "description": "Run tests; fix import/config issues (e.g., add jest.config.js)", "rationale": "Validate basic functionality"},
            {"id": "iterate-on-failures", "description": "Iterate based on test failures until green or blocked", "rationale": "Goal-driven progress"},
        ]
    # Ensure completed flags exist and are false
    for s in steps:
        if "completed" not in s:
            s["completed"] = False
    plan: Plan = {"steps": steps}
    # Persist plan incrementally
    try:
        artifacts_dir = state.get("artifacts_dir")
        if artifacts_dir:

            write_file_text(str(artifacts_dir / "plan.json"), json.dumps(plan, indent=2))
    except Exception:
        pass
    # Also persist in state for downstream nodes and attach as summary note
    try:

        _ = write_file_text  # satisfy linters
        # Add a brief note with top plan steps
        top = "; ".join([s.get("description", "") for s in steps[:3]])
        if live:
            try:
                live(f"[planner] Plan: {top}")
            except Exception:
                pass
    except Exception:
        pass
    return {**state, "plan": plan}


