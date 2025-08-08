from __future__ import annotations

from typing import List, Literal, Optional, TypedDict


class ProjectAnalysis(TypedDict, total=False):
    project_type: str
    build_commands: List[str]
    test_commands: List[str]
    run_commands: List[str]
    package_manager: Optional[str]
    dockerfile_suggested: Optional[str]


class PlanItem(TypedDict):
    id: str
    description: str
    rationale: str


class Plan(TypedDict):
    steps: List[PlanItem]


class ToolCall(TypedDict):
    tool: Literal["shell", "read", "write", "list", "search"]
    args: dict


class CodeIteration(TypedDict):
    actions: List[ToolCall]
    commit_message: str
    done: bool


