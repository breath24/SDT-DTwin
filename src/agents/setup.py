from __future__ import annotations

import json
from pathlib import Path

from ..llm import make_llm_from_settings, run_tool_loop
from ..tools.lc_tools import make_shell_tool, make_list_tool, make_read_tool, make_search_tool, make_note_write_tool, make_notes_read_tool


SETUP_PROMPT = """
You are a setup agent. Objective: prepare the repo so tests/build can run.

Inputs provide analysis with possible build/test/run commands and package manager.
Steps:
- Probe environment and note OS with a simple `shell` like `python --version`.
- If Python tests are specified, ensure `python -m pytest` works; install pytest if needed.
- If `bench.test_files` is present in the input, run ONLY those files first with: `python -m pytest -q -x --maxfail=1 <files>`. Use a timeout from `bench.test_timeout`.
- If Node tests are specified, run install via the detected package manager (npm/pnpm/yarn) and run tests.
- Log any errors and their resolutions via `note_write`. Prefer non-interactive flags.

On Windows, prefer `python -m pytest` and `where` over `which`.
Finalize when setup is reasonably complete or when blocked with clear notes.
"""


def setup_node(state: dict) -> dict:
    llm = make_llm_from_settings(state["settings"])
    repo_dir: Path = state["repo_dir"]
    analysis = state.get("analysis", {})
    transcript = state.get("transcript", [])
    live = state.get("live_update")
    events = state.get("events")

    tools = [
        make_shell_tool(repo_dir, state.get("docker")),
        make_list_tool(repo_dir),
        make_read_tool(repo_dir),
        make_search_tool(repo_dir),
        make_notes_read_tool(repo_dir, state.get("artifacts_dir")),
        make_note_write_tool(repo_dir, state.get("artifacts_dir")),
    ]

    context = {
        "analysis": analysis,
        "transcript_tail": transcript[-4:],
    }

    if live:
        live("[setup] Preparing environment...")

    result = run_tool_loop(
        llm,
        tools,
        SETUP_PROMPT,
        json.dumps(context),
        max_steps=6,
        stop_on_finalize=False,
        on_tool_start=lambda name, args: live(f"[setup] {name} {args}") if live else None,
        on_tool_end=lambda name, res: live(f"[setup] {name} -> {res}") if live else None,
        event_sink=events,
        artifacts_dir=state.get("artifacts_dir"),
        note_tag="setup",
    )

    # No special state changes; setup is best-effort. Continue to planner.
    return state


