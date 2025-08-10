from __future__ import annotations

import json
from pathlib import Path
import inspect
from typing import Any, Dict

from ..llm import make_llm_from_settings, run_tool_loop
from ..tools.lc_tools import (
    make_read_tool,
    make_write_tool,
    make_list_tool,
    make_search_tool,
    make_plan_read_tool,
    make_apply_patch_tool,
    make_lint_tool,
    make_plan_update_tool,
    make_shell_tool,
    make_note_write_tool,
    make_notes_read_tool,
    make_finalize_tool,
    make_debug_tool,
    make_replace_tool,
    make_replace_region_tool,
)
from ..config_loader import load_config, get_agent_config, get_enabled_tools, build_unified_prompt, get_agent_history_setting
from ..utils.events import summarize_last_test_event
from ..utils.progress import make_live_progress

# Tool factory mapping - maps tool names to their factory functions
TOOL_FACTORIES = {
    "read_file": make_read_tool,
    "write_file": make_write_tool,
    "list_dir": make_list_tool,
    "search": make_search_tool,
    "apply_patch": make_apply_patch_tool,
    "replace_in_file": make_replace_tool,
    "replace_region": make_replace_region_tool,
    "lint": make_lint_tool,
    "plan_read": make_plan_read_tool,
    "plan_update": make_plan_update_tool,
    "notes_read": make_notes_read_tool,
    "note_write": make_note_write_tool,
    "shell": make_shell_tool,
    "debug_env": make_debug_tool,
    "finalize": make_finalize_tool,
}






def _build_tools_from_config(repo_dir: Path, state: Dict[str, Any], config: Any) -> list:
    """Instantiate enabled tools from configuration by inspecting factory signatures.

    Passes common arguments by parameter name:
    - repo_dir
    - artifacts_dir
    - docker
    - analysis
    - config
    """
    tools: list = []
    enabled_tools = get_enabled_tools(config, "unified")
    
    for tool_name, tool_config in enabled_tools.items():
        factory = TOOL_FACTORIES.get(tool_name)
        if not factory or not callable(factory):
            continue

        try:
            sig = inspect.signature(factory)
            kwargs: Dict[str, Any] = {}
            for param_name in sig.parameters.keys():
                if param_name == "repo_dir":
                    kwargs[param_name] = repo_dir
                elif param_name == "artifacts_dir":
                    kwargs[param_name] = state.get("artifacts_dir")
                elif param_name == "docker":
                    kwargs[param_name] = state.get("docker")
                elif param_name == "analysis":
                    kwargs[param_name] = state.get("analysis")
                elif param_name == "config":
                    kwargs[param_name] = config

            tool = factory(**kwargs) if kwargs else factory()
            tools.append(tool)
        except Exception:
            # Best-effort fallback: try with repo_dir only, then skip
            try:
                tools.append(factory(repo_dir))
            except Exception:
                continue

    return tools


def unified_agent_run(state: Dict[str, Any]) -> Dict[str, Any]:
    # Load configuration
    config = load_config(config_file=state.get("config_file"), overrides=state.get("config_overrides"))
    agent_config = get_agent_config(config, "unified")
    
    llm = make_llm_from_settings(state["settings"])
    repo_dir: Path = state["repo_dir"]
    analysis = state.get("analysis", {})
    issue = state.get("issue")
    transcript = state.get("transcript", [])

    live = state.get("live_update")
    
    tools = _build_tools_from_config(repo_dir, state, config)
    enabled_tools = get_enabled_tools(config, "unified")

    # Strengthen guidance: agent should rewrite generic plan into specific steps via plan_update
    planning_guidance = (
        "If the initial plan is generic, replace it with a specific 4-7 step plan using plan_update(steps=[...]) before proceeding."
    )

    context: Dict[str, Any] = {
        "issue": {"title": getattr(issue, "title", ""), "body": getattr(issue, "body", "")},
        "analysis": analysis,
        "bench": state.get("bench", {}),
        "last_test": state.get("last_test", {}),
        "communication_note": "Send brief text messages (8-12 words) before tool calls that build momentum by connecting prior work to next actions.",
        "write_policy": (
            "Use forward slashes and full relative paths. Prefer apply_patch for multi-file edits."
        ),
        "planning_guidance": planning_guidance,
    }

    events = state.get("events")
    # Standardized live progress
    progress = make_live_progress("unified", live, agent_config.max_steps)
    _on_assistant = progress["on_assistant"]
    _on_tool_start = progress["on_tool_start"]
    _on_tool_end = progress["on_tool_end"]
    _on_step = progress["on_step"]
    if live:
        _on_assistant("Starting single-agent loop...")

    # Build dynamic prompt with tools and configuration
    unified_prompt = build_unified_prompt(config, enabled_tools)
    
    # Get agent-specific history settings
    max_history_chars = get_agent_history_setting(config, "unified", "max_history_chars")
    keep_last_messages = get_agent_history_setting(config, "unified", "keep_last_messages")
    max_tool_result_chars = get_agent_history_setting(config, "unified", "max_tool_result_chars")

    result = run_tool_loop(
      llm=llm,
      tools=tools,
      system_prompt=unified_prompt,
      user_input=json.dumps(context),
      max_steps=agent_config.max_steps,
      stop_on_finalize=True,
      # check_plan_completion=False,
      on_tool_start=_on_tool_start,
      on_tool_end=_on_tool_end,
      on_assistant=_on_assistant,
      on_step=_on_step,
      event_sink=events,
      artifacts_dir=state.get("artifacts_dir"),
      note_tag="unified",
      max_history_chars=max_history_chars,
      keep_last_messages=keep_last_messages,
      max_tool_result_chars=max_tool_result_chars,
    )

    ai = result.get("ai_message")
    finalize_args = result.get("finalize_args") or {}
    done = bool(finalize_args.get("done", False))
    commit_message = finalize_args.get("commit_message", "dev-twin unified changes")

    # Reload plan if it was updated via tools
    try:
        plan_path = Path(state.get("artifacts_dir", repo_dir.parent / "artifacts")) / "plan.json"
        if plan_path.exists():
            import json as _json
            state["plan"] = _json.loads(plan_path.read_text(encoding="utf-8"))
    except Exception:
        pass

    # Summarize last test event
    try:

        last_test = summarize_last_test_event(state.get("events") or [], artifacts_dir=state.get("artifacts_dir"))
        if last_test:
            state["last_test"] = last_test
    except Exception:
        pass

    # Record transcript including normal assistant messages
    transcript.append({
        "input": context,
        "output": {
            "finalize": finalize_args,
            "preview": getattr(ai, "content", None),
            "assistant_messages": result.get("assistant_texts", []),
        },
    })

    iteration = {"actions": [], "commit_message": commit_message, "done": done}
    return {**state, "iteration": iteration, "transcript": transcript}


