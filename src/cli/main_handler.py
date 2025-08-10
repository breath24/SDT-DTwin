"""Main command handler for dev-twin CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich import print
from dotenv import load_dotenv

from ..config import Settings
from ..config_loader import set_global_config_context
from ..github_client import GitHubClient, GitHubIssue
from ..tools import clone_repo, create_branch_commit_push, write_file_text
from ..graph import build_graph
from ..utils.logging import LiveStatus, log_panel
from ..utils.fs_extra import force_rmtree
from ..agents.unified import unified_agent_run
from ..error_handling import DevTwinError
from .commands import _parse_branch_name
from .shared import create_execution_state, parse_config_overrides


def handle_main_command(
    issue: Optional[int] = None,
    workdir: Optional[str] = None,
    docker: bool = False,
    unified: bool = False,
    config_file: Optional[str] = None,
    config_overrides: Optional[list] = None,
) -> None:
    """Handle the main dev-twin command."""
    try:
        load_dotenv()
        overrides_dict = parse_config_overrides(config_overrides)
        set_global_config_context(config_file=config_file, overrides=overrides_dict or None)

        settings = Settings.from_env()
        
        if workdir:
            settings.workdir = Path(workdir)
            
        local_mode = False
        try:
            settings.ensure()
        except Exception as e:
            print(f"[yellow]Missing env for remote run ({e}). Falling back to local dry-run.[/yellow]")
            local_mode = True

        # Setup workspace and get issue
        if not local_mode:
            gh = GitHubClient(settings.github_token, settings.repo_url)
            gh_issue = gh.find_issue_with_label("dev-twin", specific_issue=issue)
            if not gh_issue:
                print("[red]No open issue with label 'dev-twin' found.[/red]")
                raise typer.Exit(code=1)
            
            # workspace layout: workdir / repo / issue-number / repo + artifacts
            repo_root = settings.workdir / gh.repo_full_name.replace("/", "__")
            issue_root = repo_root / f"issue-{gh_issue.number}"
            repo_dir = issue_root / "repo"
            artifacts_dir = issue_root / "artifacts"
            # Clear old workspace for this issue to ensure fresh runs
            force_rmtree(issue_root)
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            
            # Clone repo
            pretty_path = str(repo_dir).replace("\\", "/")
            log_panel("Clone", f"Cloning into: {pretty_path}\\nURL: {settings.repo_url}")
            try:
                clone_repo(settings.repo_url, repo_dir, github_token=settings.github_token, artifacts_dir=artifacts_dir)
                log_panel("Clone", f"Clone completed into: {repo_dir}")
            except Exception as e:
                log_panel("Clone", f"Clone failed: {e}")
                raise
        else:
            # Prepare a local sandbox repo
            repo_root = settings.workdir / "sample_repo_root"
            issue_root = repo_root / "issue-0"
            repo_dir = issue_root / "repo"
            artifacts_dir = issue_root / "artifacts"
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            repo_dir.mkdir(parents=True, exist_ok=True)
            write_file_text(str(repo_dir / "README.md"), "# Sample Repo\\n\\nThis is a local dry-run.")
            gh_issue = GitHubIssue(number=0, title="Local dry run", body="No GitHub configured", labels=["dev-twin"])  # type: ignore

        # Prepare state
        state = create_execution_state(
            settings=settings,
            issue=gh_issue,
            repo_dir=repo_dir,
            artifacts_dir=artifacts_dir,
            config_overrides=config_overrides,
            config_file=config_file,
        )

        # Write issue.md as early as possible
        try:
            issue_md = f"# Issue\\n\\n**Title**: {gh_issue.title}\\n\\n{gh_issue.body}\\n"
            write_file_text(str(artifacts_dir / "issue.md"), issue_md)
        except Exception:
            pass

        # Docker setup if requested - simplified for now
        docker_info = None
        pre_analysis: dict = {}
        if docker and not local_mode:
            print("[yellow]Docker support simplified - running without Docker for now[/yellow]")

        # Run the workflow
        events: list = []
        with LiveStatus(artifacts_dir=artifacts_dir) as live:
            live.update("Analyzing project...")
            if local_mode:
                result = {
                    "analysis": {"project_type": "unknown", "build_commands": [], "test_commands": [], "run_commands": []},
                    "plan": {"steps": [{"id": "noop", "description": "No-op in dry run", "rationale": "No API key"}]},
                    "iteration": {"actions": [], "commit_message": "dev-twin dry run", "done": True},
                    "transcript": state["transcript"],
                }
            else:
                state["live_update"] = live.update
                state["events"] = events
                if docker_info:
                    state["docker"] = docker_info
                if pre_analysis:
                    state["analysis"] = pre_analysis
                if unified:
                    live.update("[unified] Running single-agent...")
                    result = unified_agent_run(state)
                else:
                    graph = build_graph(max_loops=10)
                    result = graph.invoke(state)
            
            live.update("Writing artifacts...")

        # Save artifacts
        write_file_text(str(artifacts_dir / "analysis.json"), json.dumps(result.get("analysis", {}), indent=2))
        write_file_text(str(artifacts_dir / "plan.json"), json.dumps(result.get("plan", {}), indent=2))
        write_file_text(str(artifacts_dir / "transcript.json"), json.dumps(result.get("transcript", []), indent=2))
        write_file_text(str(artifacts_dir / "events.json"), json.dumps(events, indent=2))

        # When done, open PR if successful
        iteration = result.get("iteration")
        if iteration and iteration.get("done") and not local_mode:
            branch = _parse_branch_name(gh_issue.number, gh_issue.title)
            tests_ran = any(
                "pytest" in e.get("args", {}).get("command", "") or "npm test" in e.get("args", {}).get("command", "")
                for e in events if e.get("tool") == "shell"
            )
            plan_steps = result.get("plan", {}).get("steps", [])
            step_lines = [f"- {s.get('description')}" for s in plan_steps[:5] if s.get("description")]
            plan_section = ("\\n".join(step_lines)) if step_lines else "- (no plan steps)"
            pr_body = (
                "Automated edits by Developer Twin.\\n\\n"
                f"Summary:\\n- Commit: {iteration.get('commit_message')}\\n- Tests ran: {'yes' if tests_ran else 'no'}\\n\\n"
                f"Plan:\\n{plan_section}"
            )
            create_branch_commit_push(
                repo_dir,
                branch,
                iteration.get("commit_message", "dev-twin changes"),
                github_token=settings.github_token,
                repo_url=settings.repo_url,
            )
            pr_title = f"dev-twin: {gh_issue.title}"
            try:
                default_base = gh._repo.default_branch  # type: ignore[attr-defined]
            except Exception:
                default_base = "main"
            pr_url = gh.create_pull_request(head=branch, base=default_base, title=pr_title, body=pr_body)
            print(f"[green]Created PR:[/green] {pr_url}")
        elif iteration and iteration.get("done") and local_mode:
            print(f"[green]Dry run complete. Would have created PR with commit '{iteration.get('commit_message')}'.[/green]")
        else:
            print("[yellow]Graph ended without 'done': true. Review transcript for progress.[/yellow]")

        log_panel("Artifacts", f"Saved to: {artifacts_dir}")
            
    except Exception as e:
        if isinstance(e, DevTwinError):
            print(f"[red]Dev-Twin Error:[/red] {e}")
        else:
            print(f"[red]Unexpected Error:[/red] {e}")
        raise typer.Exit(code=1)