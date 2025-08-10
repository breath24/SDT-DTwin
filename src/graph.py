from __future__ import annotations

from typing import Callable

from langgraph.graph import StateGraph, END

from .agents import analysis_node, planner_node, coder_node
from .agents.setup import setup_node
from .agents.test_lint import test_lint_node


def build_graph(max_loops: int = 8) -> Callable:
    graph = StateGraph(dict)
    graph.add_node("analysis", analysis_node)
    graph.add_node("planner", planner_node)
    graph.add_node("setup", setup_node)
    graph.add_node("coder", coder_node)
    graph.add_node("test_lint", test_lint_node)

    graph.set_entry_point("analysis")
    graph.add_edge("analysis", "setup")
    graph.add_edge("setup", "planner")

    def should_continue(state: dict) -> str:
        # Do not end here based on iteration.done; enforce success only after test_lint
        # basic guardrail on loop count
        if len(state.get("transcript", [])) >= max_loops:
            # Mark partial but also add a live update so it is visible in artifacts
            live = state.get("live_update")
            if live:
                try:
                    live("[coder] Max loops reached; finalizing partial work.")
                except Exception:
                    pass
            state["iteration"] = {"actions": [], "commit_message": "dev-twin partial", "done": True}
            # Also drop a marker file for post-mortem
            try:
                from .tools import write_file_text
                artifacts_dir = state.get("artifacts_dir")
                if artifacts_dir:
                    write_file_text(str(artifacts_dir / "end_marker.txt"), "Max loops reached; partial finalize")
            except Exception:
                pass
            return END
        return "coder"

    # After planning, go to coder (unless guard decides to end)
    graph.add_conditional_edges("planner", should_continue, {"coder": "coder", END: END})
    # Always run tests/lints after coder changes
    graph.add_edge("coder", "test_lint")

    def after_testlint(state: dict) -> str:
        # Declare success only if tests passed (or no tests detected) AND all plan steps are completed
        last_test = state.get("last_test") or {}
        steps = (state.get("plan") or {}).get("steps") or []
        all_complete = True if not steps else all(bool(s.get("completed")) for s in steps)
        if (last_test.get("ok") is True or last_test == {}) and all_complete:
            return END
        # Otherwise, loop back to coder with the failure/plan info so it can iterate fixes
        live = state.get("live_update")
        if live:
            try:
                msg = "[test_lint] "
                if last_test.get("ok") is True and not all_complete:
                    msg += "Tests passed but plan incomplete; returning to coder to mark/finish steps."
                else:
                    msg += "Tests failed; returning to coder to debug based on verbose output."
                live(msg)
            except Exception:
                pass
        return "coder"

    graph.add_conditional_edges("test_lint", after_testlint, {END: END, "coder": "coder"})
    return graph.compile()


