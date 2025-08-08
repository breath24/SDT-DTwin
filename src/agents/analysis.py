from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..llm import make_llm_from_settings, run_tool_loop
from ..tools import list_directory, read_file_text, search_ripgrep
from ..tools.lc_tools import make_list_tool, make_read_tool, make_search_tool
from .schemas import ProjectAnalysis
from ..utils.json_utils import extract_first_json_object


ANALYSIS_PROMPT = """
You are an expert project archeologist. Tools available: list_dir, read_file, search.
Infer project type and environment details. Use tools as needed to inspect missing files.
Return strict JSON with keys: project_type, build_commands, test_commands, run_commands, package_manager, dockerfile_suggested.

Consider common ecosystems: Node.js (npm/yarn/pnpm), Python (pip/poetry/uv), Go, Java/Gradle/Maven, Rust/Cargo, .NET, etc.
Propose a Dockerfile (string) that installs ripgrep (rg) and required runtimes.
"""


def _gather_repo_snapshot(repo_dir: Path) -> str:
    entries = list_directory(str(repo_dir))
    tops = [Path(e).name for e in entries]
    snippets = []
    for name in [
        "package.json",
        "pyproject.toml",
        "requirements.txt",
        "go.mod",
        "Cargo.toml",
        "pom.xml",
        "build.gradle",
        "Dockerfile",
        "Makefile",
        "README.md",
        "README.rst",
    ]:
        p = repo_dir / name
        if p.exists() and p.is_file():
            try:
                content = read_file_text(str(p))[:5000]
                snippets.append(f"## {name}\n{content}")
            except Exception:
                pass
    return "\n\n".join([
        "# Top-level entries:\n" + "\n".join(tops),
        "\n\n".join(snippets),
    ])


def analysis_node(state: dict) -> dict:
    # Idempotent: if analysis already present (e.g., pre-run), skip
    if "analysis" in state and state["analysis"]:
        return state
    llm = make_llm_from_settings(state["settings"])
    repo_dir: Path = state["repo_dir"]
    snapshot = _gather_repo_snapshot(repo_dir)
    tools = [make_list_tool(repo_dir), make_read_tool(repo_dir), make_search_tool(repo_dir)]
    live = state.get("live_update")
    events = state.get("events")
    if live:
        live("[analysis] Reading project files and inferring type...")
    result = run_tool_loop(
        llm,
        tools,
        ANALYSIS_PROMPT,
        snapshot,
        max_steps=2,
        on_tool_start=lambda name, args: live(f"[analysis] {name} {args}") if live else None,
        on_tool_end=lambda name, res: live(f"[analysis] {name} -> {res}") if live else None,
        event_sink=events,
        artifacts_dir=state.get("artifacts_dir"),
        note_tag="analysis",
    )
    ai = result.get("ai_message")
    text = getattr(ai, "content", None) or ""
    start = text.find("{")
    end = text.rfind("}")
    data = extract_first_json_object(text)
    # Heuristic fallback when model returns nothing or incomplete JSON
    repo_dir: Path = state["repo_dir"]
    pkg_json = repo_dir / "package.json"
    pm: str | None = None
    if (repo_dir / "pnpm-lock.yaml").exists():
        pm = "pnpm"
    elif (repo_dir / "yarn.lock").exists():
        pm = "yarn"
    elif pkg_json.exists():
        pm = "npm"

    def _read_pkg_scripts() -> dict:
        try:
            import json as _json
            return _json.loads(pkg_json.read_text(encoding="utf-8")).get("scripts", {}) if pkg_json.exists() else {}
        except Exception:
            return {}

    scripts = _read_pkg_scripts()
    build_cmds = data.get("build_commands") or ([] if not pm else ([f"{pm} install"] + ([f"{pm} run build"] if ("build" in scripts) else [])))
    test_cmds = data.get("test_commands") or ([] if not pm else ([f"{pm} test"]))
    run_cmds = data.get("run_commands") or ([] if not pm else ([f"{pm} run dev"] if ("dev" in scripts) else []))

    dockerfile = data.get("dockerfile_suggested")
    if dockerfile is None and pm:
        dockerfile = (
            "FROM node:20-alpine\n"
            "RUN apk add --no-cache bash git ca-certificates ripgrep\n"
            "WORKDIR /workspace\n"
            "COPY package*.json ./\n"
            f"RUN {pm} install\n"
            "COPY . .\n"
            "CMD [\"sh\", \"-lc\", \"echo Ready; sleep infinity\"]\n"
        )

    analysis: ProjectAnalysis = {
        "project_type": data.get("project_type") or ("node" if pm else "unknown"),
        "build_commands": build_cmds,
        "test_commands": test_cmds,
        "run_commands": run_cmds,
        "package_manager": data.get("package_manager") or pm,
        "dockerfile_suggested": dockerfile,
    }
    # Persist analysis incrementally
    try:
        artifacts_dir = state.get("artifacts_dir")
        if artifacts_dir:
            from ..tools import write_file_text
            write_file_text(str(artifacts_dir / "analysis.json"), json.dumps(analysis, indent=2))
    except Exception:
        pass
    return {**state, "analysis": analysis}


