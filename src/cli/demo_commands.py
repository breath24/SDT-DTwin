"""Demo command implementations for dev-twin CLI."""

from __future__ import annotations

import json
import shutil
from typing import Optional

import typer
from dotenv import load_dotenv
from rich import print

from ..github_client import GitHubIssue
from ..config_loader import set_global_config_context
from ..tools.shell import run_shell
from ..graph import build_graph
from ..utils.fs_extra import force_rmtree
from ..tools import write_file_text
from ..utils.logging import LiveStatus, log_panel
from ..docker_manager import ensure_docker_environment
from ..agents.analysis import analysis_node
from ..agents.unified import unified_agent_run
from .commands import _project_root, _read_issue_file
from .shared import setup_settings, parse_config_overrides, create_execution_state


def demo_run(
    name: Optional[str] = typer.Option(None, help="Specific demo project to run (default: all)"),
    workdir: Optional[str] = typer.Option(None, help="Override workdir for artifacts (defaults under demo dir)"),
    docker: bool = typer.Option(False, help="Run inside Docker using analysis-suggested Dockerfile"),
    unified: bool = typer.Option(False, help="Run a single unified agent for demos"),
    bench: bool = typer.Option(False, help="Aggregate pass/fail and output a summary across demos"),
    config_file: Optional[str] = None,
    config_overrides: Optional[list] = None,
) -> None:
    """Run the agent on one or all demo projects in `demos/`."""
    load_dotenv()
    try:
        overrides_dict = parse_config_overrides(config_overrides)
        set_global_config_context(config_file=config_file, overrides=overrides_dict or None)
        settings = setup_settings(workdir=workdir, require_github=False, config_file=config_file, config_overrides=config_overrides)
        demo_has_llm = True
    except Exception as e:
        print(f"[yellow]Demo will run in local dry-run (no LLM): {e}[/yellow]")
        demo_has_llm = False

    demos_dir = _project_root() / "demos"
    if not demos_dir.exists() or not any(demos_dir.iterdir()):
        print("[red]No demos found. Ensure the `demos/` directory is present in the project root.")
        raise typer.Exit(code=1)

    demo_names = [p.name for p in demos_dir.iterdir() if p.is_dir()]
    if name:
        if name not in demo_names:
            print(f"[red]Demo not found:[/red] {name}. Available: {', '.join(demo_names)}")
            raise typer.Exit(code=1)
        demo_names = [name]

    # Aggregate metrics (when --bench)
    runs = 0
    processed = 0
    passed_total = 0
    error_count = 0

    for demo_name in demo_names:
        # Source (committed) demo
        src_case = demos_dir / demo_name
        src_repo = src_case / "repo"
        src_issue = src_case / "issue.md"

        # Target working directory
        case_dir = settings.workdir / "demos" / demo_name
        repo_dir = case_dir / "repo"
        artifacts_dir = case_dir / "artifacts"
        force_rmtree(case_dir)
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        repo_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copytree(str(src_repo), str(repo_dir))
        except Exception as e:
            write_file_text(str(artifacts_dir / "copy_error.txt"), str(e))
            print(f"[red]Failed to copy demo repo for {demo_name}[/red]")
            continue

        title, body = _read_issue_file(src_issue)
        issue_obj = GitHubIssue(number=0, title=title, body=body, labels=["demo"])  # type: ignore

        docker_info = None
        pre_analysis: dict = {}
        if docker:
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
                    settings, repo_dir, artifacts_dir, f"demo-{demo_name}", dockerfile
                )
                pre_analysis = analysis
            else:
                docker_info, pre_analysis = None, {}

        state = create_execution_state(
            settings=settings,
            issue=issue_obj,
            repo_dir=repo_dir,
            artifacts_dir=artifacts_dir,
            config_overrides=config_overrides,
            config_file=config_file,
        )
        # Write issue.md as early as possible
        try:
            early_issue_md = f"# Issue\n\n**Title**: {issue_obj.title}\n\n{issue_obj.body}\n"
            write_file_text(str(artifacts_dir / "issue.md"), early_issue_md)
        except Exception:
            pass
        runs += 1
        events: list = []
        try:
            state["events"] = events
            if docker_info:
                state["docker"] = docker_info
            if pre_analysis:
                state["analysis"] = pre_analysis
            with LiveStatus(artifacts_dir=artifacts_dir) as live:
                state["live_update"] = live.update
                live.update(f"[analysis] Running demo: {demo_name}...")
                if demo_has_llm:
                    if unified:
                        live.update("[unified] Running single-agent demo...")
                        result = unified_agent_run(state)
                    else:
                        graph = build_graph(max_loops=10)
                        result = graph.invoke(state)
                else:
                    result = {
                        "analysis": {"project_type": "unknown", "build_commands": [], "test_commands": [], "run_commands": []},
                        "plan": {"steps": [{"id": "noop", "description": "No-op in demo dry run", "rationale": "No API key"}]},
                        "iteration": {"actions": [], "commit_message": "dev-twin demo dry run", "done": True},
                        "transcript": state["transcript"],
                    }
        except Exception as e:
            write_file_text(str(artifacts_dir / "run_error.txt"), str(e))
            error_count += 1
            continue

        # Save artifacts
        write_file_text(str(artifacts_dir / "analysis.json"), json.dumps(result.get("analysis", {}), indent=2))
        write_file_text(str(artifacts_dir / "plan.json"), json.dumps(result.get("plan", {}), indent=2))
        write_file_text(str(artifacts_dir / "transcript.json"), json.dumps(result.get("transcript", []), indent=2))
        write_file_text(str(artifacts_dir / "events.json"), json.dumps(events, indent=2))
        # Persist issue as markdown for easy reference
        try:
            issue = state.get("issue")
            title = getattr(issue, "title", "")
            body = getattr(issue, "body", "")
            issue_md = f"# Issue\n\n**Title**: {title}\n\n{body}\n"
            write_file_text(str(artifacts_dir / "issue.md"), issue_md)
        except Exception:
            pass

        iteration = result.get("iteration", {})
        
        # Check for stuck steps in plan
        stuck_steps = []
        try:
            plan_path = artifacts_dir / "plan.json"
            if plan_path.exists():
                plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
                for step in plan_data.get("steps", []):
                    if step.get("status") == "stuck":
                        stuck_steps.append(step.get("description", step.get("id", "unknown")))
        except Exception:
            pass
        
        summary = {
            "status": "success" if iteration.get("done") else "incomplete",
            "commit_message": iteration.get("commit_message"),
            "demo": demo_name,
        }
        
        if stuck_steps:
            summary["stuck_steps"] = stuck_steps
            if iteration.get("done") and iteration.get("commit_message"):
                commit_msg = iteration.get("commit_message")
                if not any(word in commit_msg.lower() for word in ["stuck", "blocked", "skip"]):
                    summary["commit_message"] = f"{commit_msg} (with {len(stuck_steps)} stuck step(s))"
        write_file_text(str(artifacts_dir / "summary.json"), json.dumps(summary, indent=2))
        try:
            log_panel("Run Summary", json.dumps(summary, indent=2))
            summary_md = f"Run summary (demo: {demo_name})\n\n- status: {summary['status']}\n- commit: {summary['commit_message']}\n"
            if stuck_steps:
                summary_md += f"- stuck steps: {len(stuck_steps)} ({', '.join(stuck_steps)})\n"
            write_file_text(str(artifacts_dir / "summary.md"), summary_md)
        except Exception:
            pass

        processed += 1
        if bool(iteration.get("done")):
            passed_total += 1

        # Cleanup Docker container if created
        if docker and docker_info and docker_info.get("container_id"):
            try:

                run_shell(f"docker rm -f {docker_info['container_id']}")
            except Exception:
                pass

    if bench:
        incomplete = processed - passed_total
        demos_root = settings.workdir / "demos"
        demos_root.mkdir(parents=True, exist_ok=True)
        demo_summary = {
            "runs": runs,
            "processed": processed,
            "passed": passed_total,
            "incomplete": incomplete,
            "errors": error_count,
        }
        try:
            write_file_text(str(demos_root / "summary.json"), json.dumps(demo_summary, indent=2))
        except Exception:
            pass
        print(
            f"[green]Demo bench completed[/green]: runs={runs}, passed={passed_total}, incomplete={incomplete}, errors={error_count}"
        )
