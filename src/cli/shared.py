"""Shared utilities for CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Dict, Any, List

from dotenv import load_dotenv

from ..config import Settings
from ..github_client import GitHubIssue
from ..config_loader import load_config, set_global_config_context
from ..tools.shell import run_shell
from ..graph import build_graph
from ..tools import write_file_text
from ..docker_manager import ensure_docker_environment
from ..agents.analysis import analysis_node
from ..agents.unified import unified_agent_run


def setup_settings(workdir: Optional[str] = None, require_github: bool = True, *, config_file: Optional[str] = None, config_overrides: Optional[List[str]] = None) -> Settings:
    """Setup and validate settings for CLI commands."""
    load_dotenv()
    settings = Settings.from_env()
    
    if workdir:
        settings.workdir = Path(workdir)
    
    # Apply global config context so downstream load_config() calls inherit CLI options
    overrides_dict = parse_config_overrides(config_overrides)
    set_global_config_context(config_file=config_file, overrides=overrides_dict or None)

    if require_github:
        settings.ensure()
    else:
        # For demo mode, only require valid provider and API key
        config = load_config(config_file=config_file, overrides=overrides_dict)
        supported_providers = config.providers.get("supported", ["google", "openai", "anthropic", "openrouter"])
        if settings.provider not in supported_providers:
            raise ValueError(f"Invalid PROVIDER: {settings.provider}. Choose one of: {', '.join(supported_providers)}")
        api_key = settings.get_current_api_key()
        if not api_key:
            raise ValueError(f"{settings.provider.upper()}_API_KEY is required when PROVIDER={settings.provider}")
    
    settings.workdir.mkdir(parents=True, exist_ok=True)
    return settings


def setup_docker_if_requested(
    docker: bool, 
    settings: Settings, 
    repo_dir: Path, 
    artifacts_dir: Path, 
    tag_hint: str
) -> tuple[Optional[Dict], Dict]:
    """Setup Docker environment if requested."""
    if not docker:
        return None, {}
    
    # Get dockerfile from analysis
    pre_state = {
        "settings": settings,
        "repo_dir": repo_dir,
        "transcript": [],
        "artifacts_dir": artifacts_dir,
        "events": [],
    }
    pre_state = analysis_node(pre_state)
    analysis = pre_state.get("analysis", {}) or {}
    dockerfile = analysis.get("dockerfile_suggested")
    
    if dockerfile:
        docker_info, build_logs = ensure_docker_environment(
            settings, repo_dir, artifacts_dir, tag_hint, dockerfile
        )
        return docker_info, analysis
    else:
        return None, {}


def run_agent_workflow(
    state: Dict[str, Any], 
    unified: bool = True, 
    max_loops: int = 10
) -> Dict[str, Any]:
    """Run either unified agent or multi-agent workflow."""
    live = state.get("live_update")
    
    if unified:
        if live:
            live("[unified] Running single-agent...")
        return unified_agent_run(state)
    else:
        if live:
            live("[multi-agent] Running workflow...")
        graph = build_graph(max_loops=max_loops)
        return graph.invoke(state)


def save_standard_artifacts(artifacts_dir: Path, result: Dict[str, Any], events: List[Dict]) -> None:
    """Save standard artifacts that all commands generate."""
    write_file_text(str(artifacts_dir / "analysis.json"), json.dumps(result.get("analysis", {}), indent=2))
    write_file_text(str(artifacts_dir / "plan.json"), json.dumps(result.get("plan", {}), indent=2))
    write_file_text(str(artifacts_dir / "transcript.json"), json.dumps(result.get("transcript", []), indent=2))
    write_file_text(str(artifacts_dir / "events.json"), json.dumps(events, indent=2))


def save_issue_markdown(artifacts_dir: Path, issue: GitHubIssue) -> None:
    """Save issue information as markdown."""
    try:
        title = getattr(issue, "title", "")
        body = getattr(issue, "body", "")
        issue_md = f"# Issue\\n\\n**Title**: {title}\\n\\n{body}\\n"
        write_file_text(str(artifacts_dir / "issue.md"), issue_md)
    except Exception:
        pass


def cleanup_docker_container(docker_info: Optional[Dict]) -> None:
    """Cleanup Docker container if it exists."""
    if docker_info and docker_info.get("container_id"):
        try:

            run_shell(f"docker rm -f {docker_info['container_id']}")
        except Exception:
            pass


def parse_config_overrides(config_overrides: Optional[List[str]]) -> Dict[str, Any]:
    """Parse CLI configuration overrides in key=value format.
    
    Args:
        config_overrides: List of strings in format "key=value" or "nested.key=value"
    
    Returns:
        Dictionary of parsed overrides
    """
    if not config_overrides:
        return {}
    
    overrides = {}
    for override in config_overrides:
        if "=" not in override:
            continue
        
        key, value = override.split("=", 1)
        key = key.strip()
        value = value.strip()
        
        # Try to convert value to appropriate type
        if value.lower() in ("true", "false"):
            value = value.lower() == "true"
        elif value.isdigit():
            value = int(value)
        elif value.replace(".", "", 1).isdigit():
            value = float(value)
        # Otherwise keep as string
        
        overrides[key] = value
    
    return overrides


def create_execution_state(
    settings: Settings,
    issue: GitHubIssue,
    repo_dir: Path,
    artifacts_dir: Path,
    docker_info: Optional[Dict] = None,
    pre_analysis: Optional[Dict] = None,
    extra_data: Optional[Dict] = None,
    config_overrides: Optional[List[str]] = None,
    config_file: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a standard execution state for agents."""
    state = {
        "settings": settings,
        "issue": issue,
        "repo_dir": repo_dir,
        "transcript": [],
        "artifacts_dir": artifacts_dir,
        "events": [],
    }
    
    if docker_info:
        state["docker"] = docker_info
    if pre_analysis:
        state["analysis"] = pre_analysis
    if extra_data:
        state.update(extra_data)
    if config_overrides:
        state["config_overrides"] = parse_config_overrides(config_overrides)
    if config_file:
        state["config_file"] = config_file
    
    return state
