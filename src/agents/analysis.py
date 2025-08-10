from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..llm import make_llm_from_settings, run_tool_loop
from ..tools import list_directory, read_file_text
from ..tools.lc_tools import (
    make_list_tool,
    make_read_tool,
    make_search_tool,
    make_note_write_tool,
    make_notes_read_tool,
    make_finalize_tool,
)
from .schemas import ProjectAnalysis
from ..utils.json_utils import extract_first_json_object
# Moved constants to config
from ..config_loader import load_config, get_agent_config, load_prompt, get_agent_history_setting
from ..tools import write_file_text
from ..utils.progress import make_live_progress

# Language detection using pygments
try:
    from pygments.lexers import get_lexer_for_filename
    from pygments.util import ClassNotFound
    PYGMENTS_AVAILABLE = True
except ImportError:
    PYGMENTS_AVAILABLE = False





def _detect_language_pygments(repo_dir: Path) -> tuple[str, float]:
    """Use pygments to detect the most common language in the repository."""
    if not PYGMENTS_AVAILABLE:
        return "unknown", 0.0
    
    language_counts = {}
    total_files = 0
    
    # Sample files from common locations
    file_patterns = [
        "*.py", "*.js", "*.ts", "*.jsx", "*.tsx", "*.java", "*.go", "*.rs", 
        "*.c", "*.cpp", "*.h", "*.hpp", "*.rb", "*.php", "*.cs", "*.swift"
    ]
    
    try:
        for pattern in file_patterns:
            for file_path in list(repo_dir.glob(pattern))[:10]:  # Limit to 10 files per pattern
                if file_path.is_file() and file_path.stat().st_size < 100000:  # Skip very large files
                    try:
                        lexer = get_lexer_for_filename(str(file_path))
                        lang_name = lexer.name.lower()
                        
                        # Normalize language names
                        if "python" in lang_name:
                            lang_name = "python"
                        elif "javascript" in lang_name or "typescript" in lang_name:
                            lang_name = "javascript"
                        elif "java" in lang_name:
                            lang_name = "java"
                        elif "go" in lang_name:
                            lang_name = "go"
                        elif "rust" in lang_name:
                            lang_name = "rust"
                        elif "c++" in lang_name or "cpp" in lang_name:
                            lang_name = "cpp"
                        elif "c" in lang_name:
                            lang_name = "c"
                        
                        language_counts[lang_name] = language_counts.get(lang_name, 0) + 1
                        total_files += 1
                    except (ClassNotFound, Exception):
                        continue
    except Exception:
        pass
    
    if not language_counts or total_files == 0:
        return "unknown", 0.0
    
    # Find the most common language
    most_common = max(language_counts.items(), key=lambda x: x[1])
    confidence = most_common[1] / total_files
    
    return most_common[0], confidence


def _detect_stack(repo_dir: Path) -> dict[str, Any]:
    """Simplified stack detection: just language + basic package manager detection."""
    # Use pygments for primary language detection
    pygments_lang, pygments_confidence = _detect_language_pygments(repo_dir)
    
    # Simple package manager detection for Node.js
    pm = None
    if (repo_dir / "package.json").exists():
        if (repo_dir / "pnpm-lock.yaml").exists():
            pm = "pnpm"
        elif (repo_dir / "yarn.lock").exists():
            pm = "yarn"
        else:
            pm = "npm"
    
    # Use pygments result as primary, with simple overrides for obvious cases
    lang = pygments_lang
    confidence = "high" if pygments_confidence > 0.6 else ("medium" if pygments_confidence > 0.3 else "low")
    
    # Only override pygments for very obvious cases
    if (repo_dir / "package.json").exists() and pygments_lang in ["unknown", "javascript"]:
        lang = "javascript"  # Node.js projects
        confidence = "high"
    elif (repo_dir / "go.mod").exists():
        lang = "go"
        confidence = "high"
    elif (repo_dir / "Cargo.toml").exists():
        lang = "rust" 
        confidence = "high"
    elif pygments_lang == "unknown" and any((repo_dir / f).exists() for f in ["setup.py", "pyproject.toml"]):
        lang = "python"
        confidence = "medium"
    
    return {
        "language": lang,
        "package_manager": pm,
        "confidence": confidence,
        "pygments_detection": {
            "language": pygments_lang,
            "confidence": pygments_confidence
        } if PYGMENTS_AVAILABLE else None,
    }


def _generate_dockerfile(stack_info: dict[str, Any], config: Any) -> str:
    """Generate a minimal Dockerfile with ripgrep and basic tools. Let AI handle specifics."""

    workspace_dir = config.docker.get("workspace_dir", "/workspace")
    sleep_cmd = config.docker.get("sleep_cmd", "sleep infinity")
    
    lang = stack_info.get("language", "unknown")
    pm = stack_info.get("package_manager")
    
    if lang == "javascript" and pm:
        return f"""FROM node:20-alpine
RUN apk add --no-cache bash git ripgrep build-base
WORKDIR {workspace_dir}
COPY . .
CMD ["sh", "-lc", "echo Ready; {sleep_cmd}"]
"""
    
    elif lang == "java":
        return f"""FROM eclipse-temurin:17-jdk-jammy
RUN apt-get update && apt-get install -y --no-install-recommends ripgrep git build-essential && rm -rf /var/lib/apt/lists/*
WORKDIR {workspace_dir}
COPY . .
CMD ["sh", "-lc", "echo Ready; {sleep_cmd}"]
"""
    
    elif lang == "go":
        return f"""FROM golang:1.22-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends ripgrep git && rm -rf /var/lib/apt/lists/*
WORKDIR {workspace_dir}
COPY . .
CMD ["sh", "-lc", "echo Ready; {sleep_cmd}"]
"""
    
    elif lang == "rust":
        return f"""FROM rust:1-slim
RUN apt-get update && apt-get install -y --no-install-recommends ripgrep git build-essential pkg-config libssl-dev && rm -rf /var/lib/apt/lists/*
WORKDIR {workspace_dir}
COPY . .
CMD ["sh", "-lc", "echo Ready; {sleep_cmd}"]
"""
    
    elif lang == "cpp" or lang == "c":
        return f"""FROM gcc:latest
RUN apt-get update && apt-get install -y --no-install-recommends ripgrep git cmake make && rm -rf /var/lib/apt/lists/*
WORKDIR {workspace_dir}
COPY . .
CMD ["sh", "-lc", "echo Ready; {sleep_cmd}"]
"""
    
    # Default to Python (most common case) with better scientific package support
    return f"""FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends git ripgrep build-essential && rm -rf /var/lib/apt/lists/*
WORKDIR {workspace_dir}
# Pre-install common scientific packages to avoid build issues
RUN pip install --upgrade pip setuptools wheel
RUN pip install numpy scipy matplotlib pytest pytest-cov
COPY . .
CMD ["sh", "-lc", "echo Ready; {sleep_cmd}"]
"""


def _gather_repo_snapshot(repo_dir: Path, config: Any) -> str:
    entries = list_directory(str(repo_dir))
    tops = [Path(e).name for e in entries]
    snippets = []
    config_files = config.file_types.get("config_files", ["package.json", "pyproject.toml", "requirements.txt"])
    docs_files = config.file_types.get("docs_files", ["README.md", "README.rst", "docs/", "documentation/"])
    config_and_docs = list(config_files) + list(docs_files)
    for name in config_and_docs:
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
    
    repo_dir: Path = state["repo_dir"]
    live = state.get("live_update")
    events = state.get("events")
    
    # Load configuration
    config = load_config(config_file=state.get("config_file"), overrides=state.get("config_overrides"))
    agent_config = get_agent_config(config, "analysis")
    
    # Pre-analyze stack using reliable static detection
    if live:
        live("[analysis] Detecting project stack...")
    stack_info = _detect_stack(repo_dir)
    
    # Always generate a Dockerfile based on static detection
    dockerfile = _generate_dockerfile(stack_info, config)
    
    if live:
        confidence_str = f" ({stack_info['confidence']} confidence)"
        live(f"[analysis] Detected {stack_info['language']} project{confidence_str}, running LLM analysis...")
    
    llm = make_llm_from_settings(state["settings"])
    snapshot = _gather_repo_snapshot(repo_dir, config)

    # Progress helpers for better UI feedback
    progress = make_live_progress("analysis", live, agent_config.max_steps)
    _on_assistant = progress["on_assistant"]
    _on_tool_start = progress["on_tool_start"]
    _on_tool_end = progress["on_tool_end"]
    _on_step = progress["on_step"]
    
    # Add stack info to the snapshot for better LLM context
    stack_context = f"\n\n# Static Analysis Results\nDetected language: {stack_info['language']}\nPackage manager: {stack_info.get('package_manager', 'none')}\nConfidence: {stack_info['confidence']}"
    snapshot += stack_context
    
    tools = [
        make_list_tool(repo_dir),
        make_read_tool(repo_dir),
        make_search_tool(repo_dir),
        make_notes_read_tool(repo_dir, state.get("artifacts_dir")),
        make_note_write_tool(repo_dir, state.get("artifacts_dir")),
        make_finalize_tool(),
    ]
    
    # Load prompt from file
    analysis_prompt = load_prompt("analysis")
    
    # Get agent-specific history settings
    max_history_chars = get_agent_history_setting(config, "analysis", "max_history_chars")
    keep_last_messages = get_agent_history_setting(config, "analysis", "keep_last_messages")
    max_tool_result_chars = get_agent_history_setting(config, "analysis", "max_tool_result_chars")
    
    result = run_tool_loop(
        llm,
        tools,
        analysis_prompt,
        snapshot,
        max_steps=agent_config.max_steps,
        stop_on_finalize=True,
        on_tool_start=_on_tool_start,
        on_tool_end=_on_tool_end,
        on_assistant=_on_assistant,
        on_step=_on_step,
        event_sink=events,
        artifacts_dir=state.get("artifacts_dir"),
        note_tag="analysis",
        max_history_chars=max_history_chars,
        keep_last_messages=keep_last_messages,
        max_tool_result_chars=max_tool_result_chars,
    )
    
    ai = result.get("ai_message")
    text = getattr(ai, "content", None) or ""
    data = extract_first_json_object(text)
    
    # Use static detection results
    lang = stack_info["language"]
    pm = stack_info.get("package_manager")
    
    # Force Dockerfile generation - use LLM suggestion if good, otherwise static fallback
    llm_dockerfile = data.get("dockerfile_suggested")
    if llm_dockerfile and len(llm_dockerfile.strip()) > 50:  # LLM provided a decent Dockerfile
        final_dockerfile = llm_dockerfile
    else:
        final_dockerfile = dockerfile  # Use our static generation
    
    # Let AI determine build/test commands - just provide basic fallbacks
    build_cmds = data.get("build_commands") or []
    test_cmds = data.get("test_commands") or []
    run_cmds = data.get("run_commands") or []

    # Build relevant_files baseline (tests/configs) to help downstream coders
    # Seed relevant_files with benchmark-provided test files (if any) to surface them early
    relevant_files: list[str] = []
    try:
        bench = state.get("bench", {}) or {}
        for tf in bench.get("test_files", []) or []:
            relevant_files.append(str(tf))
    except Exception:
        pass
    try:
        # Common test dirs/files
        test_directories = config.testing.get("test_directories", ["tests", "test", "__tests__"])
        for name in test_directories:
            p = repo_dir / name
            if p.exists():
                relevant_files.append(name)
        # Top-level configs or entry points
        for name in ["requirements.txt", "pyproject.toml", "package.json", "setup.cfg", "pytest.ini", "README.md"]:
            if (repo_dir / name).exists():
                relevant_files.append(name)
    except Exception:
        pass

    # Issue-specific relevance based on issue text (if available in state)
    relevant_issue: list[str] = []
    try:
        issue = state.get("issue")
        body = (getattr(issue, "body", "") or "") + "\n" + (getattr(issue, "title", "") or "")
        for p in relevant_files:
            name = str(p).lower()
            if any(tok in name for tok in ["file", "upload", "permission", "django", "storage", "test"]):
                relevant_issue.append(str(p))
    except Exception:
        pass

    # Simple test strategy - let AI figure out the details
    bench = state.get("bench", {}) or {}
    test_strategy = data.get("test_strategy") or {
        "runner": "pytest",  # sensible default
        "files": bench.get("test_files", []),
        "args": ["-q"],
    }

    analysis: ProjectAnalysis = {
        "project_type": data.get("project_type") or lang,
        "build_commands": build_cmds,
        "test_commands": test_cmds,
        "run_commands": run_cmds,
        "package_manager": data.get("package_manager") or pm,
        "dockerfile_suggested": final_dockerfile,
        "relevant_files": sorted(set((data.get("relevant_files") or []) + relevant_files)),
        "relevant_files_issue": sorted(set((data.get("relevant_files_issue") or []) + relevant_issue)),
        "setup_steps": data.get("setup_steps") or [
            f"Set up {lang} environment",
            "Install dependencies",
            "Run tests",
        ],
        "test_strategy": test_strategy,
        "framework_repo": bool(data.get("framework_repo", False)),
        "pytest_config_present": bool(data.get("pytest_config_present", False)),
        "django_settings_required": bool(data.get("django_settings_required", False)),
        "env": data.get("env") or {},
        "venv_recommended": True,
    }
    # Attempt dynamic lint discovery for downstream nodes
    try:
        from .test_lint import _discover_lint_commands
        analysis["lint_commands"] = _discover_lint_commands(repo_dir)
    except Exception:
        pass
    # Persist analysis incrementally
    try:
        artifacts_dir = state.get("artifacts_dir")
        if artifacts_dir:

            write_file_text(str(artifacts_dir / "analysis.json"), json.dumps(analysis, indent=2))
    except Exception:
        pass
    # Drop a short note for downstream nodes
    try:
        tn = analysis.get("test_strategy", {}).get("runner") or (analysis.get("test_commands") or ["?"])[0]
        setup = ", ".join((analysis.get("setup_steps") or [])[:3])
        rel = (analysis.get("relevant_files_issue") or []) + (analysis.get("relevant_files") or [])
        rel = ", ".join(rel[:6])
        note = f"runner: {tn}; setup: {setup or 'n/a'}; files: {rel or 'n/a'}"
        try:
            note_write = make_note_write_tool(state["repo_dir"], state.get("artifacts_dir"))
            _ = note_write.invoke({"topic": "analysis", "content": note})
        except Exception:
            pass
    except Exception:
        pass
    return {**state, "analysis": analysis}


