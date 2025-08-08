from __future__ import annotations

from typing import Callable

from langgraph.graph import StateGraph, END

from .agents import analysis_node, planner_node, coder_node
from .agents.setup import setup_node


def build_graph(max_loops: int = 8) -> Callable:
    graph = StateGraph(dict)
    graph.add_node("analysis", analysis_node)
    graph.add_node("planner", planner_node)
    graph.add_node("setup", setup_node)
    graph.add_node("coder", coder_node)

    graph.set_entry_point("analysis")
    graph.add_edge("analysis", "setup")
    graph.add_edge("setup", "planner")

    def should_continue(state: dict) -> str:
        iteration = state.get("iteration")
        if iteration and iteration.get("done"):
            return END
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

    graph.add_conditional_edges("planner", should_continue, {"coder": "coder", END: END})
    graph.add_conditional_edges("coder", should_continue, {"coder": "coder", END: END})
    return graph.compile()


