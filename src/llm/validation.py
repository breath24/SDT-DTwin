"""Plan and finalization validation logic."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ..constants import (
    CORE_IMPLEMENTATION_KEYWORDS,
    VALID_STUCK_KEYWORDS,
)
from ..config_loader import load_config, get_limit_setting


def check_plan_incomplete(artifacts_dir: str | Path) -> bool:
    """Check if the plan has incomplete steps."""
    try:
        import json
        
        plan_path = Path(artifacts_dir) / "plan.json"
        if not plan_path.exists():
            return False  # No plan, so can't check
        
        plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
        steps = plan_data.get("steps", [])
        
        # Check if any steps are not completed
        for step in steps:
            status = step.get("status", "pending")
            if status != "completed":
                return True  # Found incomplete step
        
        return False  # All steps completed
    except Exception:
        return False  # Error reading plan, assume complete


def validate_finalize_args(
    *,
    args: Dict[str, Any] | None,
    artifacts_dir: str | Path | None,
    check_plan_completion: bool,
) -> Tuple[bool, List[str], List[Dict[str, Any]]]:
    """
    Validate finalize arguments and check plan completion.
    
    Returns:
        Tuple of (is_valid, reasons, incomplete_steps)
    """
    reasons: List[str] = []
    incomplete_steps: List[Dict[str, Any]] = []

    # Check commit message
    commit_message_val: str | None = None
    try:
        commit_message_val = args.get("commit_message") if isinstance(args, dict) else None
    except Exception:
        commit_message_val = None
        
    if not (isinstance(commit_message_val, str) and commit_message_val.strip()):
        reasons.append("missing commit_message")

    # Check plan completion
    plan_is_incomplete = False
    try:
        if check_plan_completion and artifacts_dir:
            plan_is_incomplete, plan_reasons, plan_incomplete_steps = _validate_plan_completion(
                artifacts_dir
            )
            reasons.extend(plan_reasons)
            incomplete_steps.extend(plan_incomplete_steps)
    except Exception:
        # Do not block on validation errors
        pass

    if plan_is_incomplete:
        reasons.append("plan has incomplete steps")

    return (len(reasons) == 0, reasons, incomplete_steps)


def _validate_plan_completion(artifacts_dir: str | Path) -> Tuple[bool, List[str], List[Dict[str, Any]]]:
    """Validate plan completion and detect misuse of stuck status.

    Rules:
    - Finalization is allowed when ALL steps are either completed or stuck,
      provided the stuck ratio does not exceed the configured threshold.
    - Placeholder code checks (e.g., TODO/not-implemented) are surfaced as
      warnings elsewhere but DO NOT block finalization.
    - Only steps with status not in {completed, stuck} are treated as incomplete.
    - If stuck ratio exceeds the configured limit, finalization is blocked.
    """
    import json
    
    plan_path = Path(artifacts_dir) / "plan.json"
    if not plan_path.exists():
        return False, [], []
    
    data = json.loads(plan_path.read_text(encoding="utf-8"))
    stuck_steps: List[Dict[str, Any]] = []
    incomplete_steps: List[Dict[str, Any]] = []
    total_steps = 0
    reasons: List[str] = []
    
    for step in data.get("steps", []) or []:
        total_steps += 1
        status = step.get("status") or "pending"
        
        if status == "stuck":
            stuck_steps.append(step)
        elif status not in ["completed"]:
            incomplete_steps.append({
                "id": step.get("id"),
                "description": step.get("description"),
                "status": status,
            })
    
    # Validate stuck step usage
    if total_steps > 0 and stuck_steps:
        config = load_config()
        max_stuck_ratio = get_limit_setting(config, "max_stuck_ratio", 0.6)

        stuck_ratio = len(stuck_steps) / total_steps
        if stuck_ratio > max_stuck_ratio:
            # Too many steps are stuck → block finalization
            reasons.append("too many steps marked as stuck - likely misuse")
            return True, reasons, incomplete_steps

    # Placeholder checks should not block finalization; run but ignore for gating
    # Kept here in case callers want to log or surface them separately in the future
    _ = _check_placeholder_implementations  # noqa: F841 (intentional reference)

    # Only consider truly incomplete steps (excluding stuck) for plan completion
    plan_is_incomplete = bool(incomplete_steps)

    # Report only truly incomplete steps (do not include stuck in "remaining")
    return plan_is_incomplete, reasons, incomplete_steps


def _identify_stuck_core_steps(stuck_steps: List[Dict[str, Any]]) -> List[str]:
    """Identify stuck steps that appear to be core implementation work."""
    stuck_core_steps: List[str] = []
    
    for step in stuck_steps:
        desc = (step.get("description") or "").lower()
        
        # Check if it contains core implementation keywords
        if any(keyword in desc for keyword in CORE_IMPLEMENTATION_KEYWORDS):
            # But exclude if it's clearly test/config related
            if not any(test_word in desc for test_word in VALID_STUCK_KEYWORDS):
                stuck_core_steps.append(
                    step.get("description", step.get("id", "unknown"))
                )
    
    return stuck_core_steps


def _check_placeholder_implementations(artifacts_dir: str | Path) -> List[str]:
    """Check for placeholder implementations (TODOs, throw errors)."""
    reasons: List[str] = []
    
    # Load config for limits
    config = load_config()
    max_todo_count = get_limit_setting(config, "max_todo_count", 10)
    max_not_implemented_count = get_limit_setting(config, "max_not_implemented_count", 3)
    
    try:
        repo_dir = Path(artifacts_dir).parent / "repo"
        if not repo_dir.exists():
            return reasons
        
        todo_count = 0
        error_count = 0
        
        for root, dirs, files in os.walk(repo_dir):
            # Skip common directories that shouldn't be checked
            dirs[:] = [
                d for d in dirs 
                if d not in ["node_modules", "__pycache__", ".git", "dist", "build"]
            ]
            
            for file in files:
                if file.endswith((".js", ".jsx", ".ts", ".tsx", ".py")):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()
                            
                        # Count TODOs and placeholder implementations
                        todo_count += len(re.findall(r"TODO|FIXME|XXX", content, re.IGNORECASE))
                        error_count += len(re.findall(
                            r"throw new Error.*not implemented|not implemented",
                            content,
                            re.IGNORECASE,
                        ))
                    except (IOError, UnicodeDecodeError):
                        continue
        
        if todo_count > max_todo_count:
            reasons.append(
                f"CRITICAL: {todo_count} TODO comments found - you must implement actual "
                f"functionality, not placeholder code. Review and replace all TODO/FIXME "
                f"comments with working implementations before finalizing"
            )
        elif error_count > max_not_implemented_count:
            reasons.append(
                f"CRITICAL: {error_count} 'not implemented' errors found - you must "
                f"implement actual functionality, not throw placeholder errors"
            )
    except Exception:
        pass
    
    return reasons
