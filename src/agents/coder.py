from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..llm import make_llm_from_settings, run_tool_loop
from ..tools.lc_tools import (
    make_read_tool,
    make_write_tool,
    make_list_tool,
    make_search_tool,
    make_shell_tool,
    make_finalize_tool,
    make_note_write_tool,
    make_notes_read_tool,
)
from .schemas import CodeIteration


CODER_PROMPT = """
You are an automated coding agent.

Available tools: shell, read_file, write_file, list_dir, search, notes_read, note_write, finalize.

Primary objective:
- Make concrete edits that implement the plan and resolve TODOs/Not Implemented errors. Prefer minimal, incremental edits that keep the app and tests runnable.

Guidelines:
- Act step-by-step. Prefer small, safe changes; use non-interactive flags in shell.
- Always `read_file` first to verify context before writing; then proceed to `write_file` to implement.
- If a file does not exist, create it via `write_file` and include a short header comment.
- Use forward slashes in paths (JSON strings), relative to repo root.
- Use `note_write` to log observations, hypotheses, command attempts, errors, and next steps. At the start of each step, call `notes_read` to recall prior attempts; incorporate notes into your next actions.
- When encountering TODOs or thrown errors, implement the smallest functional version (stubs with real returns) and wire it into the app/tests.
- After a few reads, you must perform `write_file` changes. Avoid read-only loops.
 - When any command/test fails or succeeds, add a `note_write` entry summarizing the outcome and the next step.
 - When you complete a coherent increment, add a `note_write` entry describing what was completed before finalizing.

OS-specific:
- On Windows, prefer `python -m pytest` instead of `pytest`. Use `where` instead of `which`.

Loop avoidance:
- If `read_file` returns `NOT_FOUND:`, do not keep retrying; search/list or create the file.
- After 2 reads of the same path, take a different action (write, search, or shell).
- If the same shell command fails twice, note the failure and try an adjusted command.

Completion:
- When a coherent increment is implemented (or you are blocked), call `finalize` with a clear commit message and `done`: true.
"""


def coder_node(state: dict) -> dict:
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
        make_shell_tool(repo_dir, state.get("docker")),
        make_notes_read_tool(repo_dir, artifacts_dir),
        make_note_write_tool(repo_dir, artifacts_dir),
        make_finalize_tool(),
    ]
    # Use tool loop so tools actually execute in multiple steps and we can detect finalize
    import platform, json as _json
    # Read recent notes (if present) to prime the model with context without tool calls
    notes_recent: list[str] = []
    try:
        notes_path = (state.get("artifacts_dir", repo_dir.parent / "artifacts") / ".devtwin_notes.jsonl")
        if notes_path.exists():
            lines = notes_path.read_text(encoding="utf-8").splitlines()
            for raw in reversed(lines[-50:]):
                try:
                    obj = _json.loads(raw)
                    notes_recent.append(f"[{obj.get('ts')}] {obj.get('topic')}: {obj.get('content')}")
                except Exception:
                    continue
            notes_recent = list(reversed(notes_recent[-20:]))
    except Exception:
        pass
    # Embed the full plan JSON verbatim to ensure it is always visible
    plan_text_verbatim = ""
    try:
        plan_text_verbatim = _json.dumps(plan, ensure_ascii=False, indent=2)
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
        "write_policy": (
            "Always provide full relative paths with forward slashes when writing files (e.g., 'src/components/Dashboard.jsx'). "
            "Do not use bare filenames. After reading a few files, perform targeted write_file edits to implement TODOs and remove thrown errors."
        ),
    }
    live = state.get("live_update")
    events = state.get("events")
    if live:
        live("[coder] Working on implementation...")
    # Resume prior conversation to prevent context reset between iterations
    # Reuse prior conversation but cap history to avoid runaway context growth
    prior_messages = state.get("coder_messages")
    if isinstance(prior_messages, list) and len(prior_messages) > 60:
        prior_messages = prior_messages[-60:]
    result = run_tool_loop(
        llm,
        tools,
        CODER_PROMPT,
        json.dumps(context),
        max_steps=50,
        stop_on_finalize=True,
        on_tool_start=lambda name, args: live(f"[coder] {name} {args}") if live else None,
        on_tool_end=lambda name, res: live(f"[coder] {name} -> {res}") if live else None,
        event_sink=events,
        artifacts_dir=state.get("artifacts_dir"),
        initial_messages=prior_messages,
        extra_user_message=json.dumps({"continue": True, "context": context}),
        note_tag="coder",
    )
    ai = result.get("ai_message")
    text = getattr(ai, "content", None) or ""
    finalize_args = result.get("finalize_args") or {}
    done = bool(finalize_args.get("done", False))
    commit_message = finalize_args.get("commit_message", "dev-twin changes")

    iteration: CodeIteration = {
        "actions": [],
        "commit_message": commit_message,
        "done": done,
    }

    # If test runner loops were suppressed or repeated without success, finalize partial work
    if not done:
        try:
            txt_lower = (text or "").lower()
        except Exception:
            txt_lower = ""
        if ("skipped_repeat_group" in txt_lower) or ("test_runner_suppressed" in txt_lower):
            iteration = {
                "actions": [],
                "commit_message": "Partial implementation committed; suppressed repeated test runs to avoid infinite loop.",
                "done": True,
            }

    transcript.append({"input": context, "output": {"text": text, "finalize": finalize_args}})
    # Persist transcript incrementally
    try:
        artifacts_dir = state.get("artifacts_dir")
        if artifacts_dir:
            from ..tools import write_file_text
            write_file_text(str(artifacts_dir / "transcript.json"), json.dumps(transcript, indent=2))
    except Exception:
        pass
    # Persist conversation messages for continuity in the next loop
    state["coder_messages"] = result.get("messages") or prior_messages
    return {**state, "iteration": iteration, "transcript": transcript, "coder_messages": state["coder_messages"]}


