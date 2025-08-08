from __future__ import annotations

import json
from typing import Any

from ..llm import make_llm_from_settings, run_tool_loop
from ..tools.lc_tools import make_list_tool, make_read_tool, make_search_tool
from .schemas import Plan
from ..utils.json_utils import extract_first_json_object


PLANNER_PROMPT = (
    "You are a senior tech lead. Given a GitHub issue and project analysis, create an actionable plan.\n\n"
    "Return strict JSON with key `steps` being a list of objects {id, description, rationale}.\n"
    "Keep steps minimal, logically ordered, and test-focused. Avoid vague steps.\n\n"
    "If analysis is missing or empty, infer a minimal plan based on repository cues (e.g., package.json)."
)


def planner_node(state: dict) -> dict:
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
    ]
    live = state.get("live_update")
    events = state.get("events")
    if live:
        live("[planner] Generating plan...")
    result = run_tool_loop(
        llm,
        tools,
        PLANNER_PROMPT,
        json.dumps(inputs),
        max_steps=2,
        on_tool_start=lambda name, args: live(f"[planner] {name} {args}") if live else None,
        on_tool_end=lambda name, res: live(f"[planner] {name} -> {res}") if live else None,
        event_sink=events,
        artifacts_dir=state.get("artifacts_dir"),
        note_tag="planner",
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
            {"id": "wire-tests", "description": "Run jest and fix simple import/config issues", "rationale": "Validate basic functionality"},
        ]
    plan: Plan = {"steps": steps}
    # Persist plan incrementally
    try:
        artifacts_dir = state.get("artifacts_dir")
        if artifacts_dir:
            from ..tools import write_file_text
            write_file_text(str(artifacts_dir / "plan.json"), json.dumps(plan, indent=2))
    except Exception:
        pass
    # Also persist in state for downstream nodes and attach as summary note
    try:
        from ..tools import write_file_text
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


