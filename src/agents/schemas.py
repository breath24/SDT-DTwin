from __future__ import annotations

from typing import Any, List, Literal, Optional, TypedDict
from pathlib import Path


class TestStrategy(TypedDict, total=False):
    runner: Literal["pytest", "django_manage", "other"]
    files: List[str]
    args: List[str]


class ProjectAnalysis(TypedDict, total=False):
    project_type: str
    build_commands: List[str]
    test_commands: List[str]
    run_commands: List[str]
    package_manager: Optional[str]
    dockerfile_suggested: Optional[str]
    relevant_files: List[str]
    relevant_files_issue: List[str]
    setup_steps: List[str]
    test_strategy: TestStrategy
    framework_repo: bool
    pytest_config_present: bool
    django_settings_required: bool
    env: dict
    venv_recommended: bool


class PlanItem(TypedDict, total=False):
    id: str
    description: str
    rationale: str
    completed: bool
    status: Literal["pending", "in_progress", "completed", "stuck"]


class Plan(TypedDict):
    steps: List[PlanItem]


class ToolCall(TypedDict):
    tool: Literal["shell", "read", "write", "list", "search"]
    args: dict


class CodeIteration(TypedDict):
    actions: List[ToolCall]
    commit_message: str
    done: bool


class RunState(TypedDict, total=False):
    settings: Any
    issue: Any
    repo_dir: Path
    artifacts_dir: Path
    analysis: ProjectAnalysis
    plan: "Plan"
    last_test: dict
    bench: dict
    events: List[dict]
    live_update: Any
    coder_messages: List[Any]
    transcript: List[Any]
    iteration: CodeIteration

