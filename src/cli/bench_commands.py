"""Benchmark command implementations for dev-twin CLI."""

from __future__ import annotations

import json
import tempfile
from typing import Optional

import typer
from rich import print
from datasets import load_dataset
from git import Repo as GitRepo

from ..github_client import GitHubIssue
from ..graph import build_graph
from ..utils.fs_extra import force_rmtree
from ..tools import write_file_text, clone_repo
from ..utils.logging import LiveStatus, log_panel
from ..docker_manager import ensure_docker_environment
from ..agents.analysis import analysis_node
from ..agents.unified import unified_agent_run
from ..tools.shell import run_shell
from ..config_loader import load_config, set_global_config_context
from .shared import setup_settings, parse_config_overrides


def _extract_test_files(patch_text: str) -> list[str]:
    """Extract test file paths from a patch."""
    files: list[str] = []
    for line in patch_text.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:].strip()
            if path and ("test" in path or path.startswith("tests/")):
                files.append(path)
    return sorted(set(files))


def _example_type(e: dict) -> str:
    """Determine the type of benchmark example."""
    if e.get("FAIL_TO_PASS") or e.get("fail_to_pass"):
        return "fail"
    if e.get("PASS_TO_PASS") or e.get("pass_to_pass"):
        return "pass"
    t = (e.get("problem_type") or e.get("category") or "").lower()
    if "fail" in t:
        return "fail"
    if "pass" in t:
        return "pass"
    return "unknown"


def bench_run(
    subset: str = typer.Option("princeton-nlp/SWE-bench_Lite", help="HF dataset path"),
    split: str = typer.Option("test", help="Dataset split"),
    limit: Optional[int] = typer.Option(None, help="Limit number of examples"),
    workdir: Optional[str] = typer.Option(None, help="Override workdir"),
    skip_completed: bool = typer.Option(False, help="Skip examples already completed"),
    skip_n: int = typer.Option(0, help="Skip the first N examples in the split"),
    skip_repo: Optional[str] = typer.Option(None, help="Skip all examples whose repo contains this substring (e.g., 'astropy/astropy')"),
    only_type: str = typer.Option("all", help="Filter by type: 'fail', 'pass', or 'all'"),
    apply_test_patch: bool = typer.Option(True, help="Apply test_patch to add failing tests before running"),
    test_timeout: int = typer.Option(120, help="Timeout in seconds for individual test runs"),
    docker: bool = typer.Option(False, help="Run inside Docker using analysis-suggested Dockerfile"),
    unified: bool = typer.Option(False, help="Run a single unified agent instead of the multi-agent graph"),
    config_file: Optional[str] = None,
    config_overrides: Optional[list] = None,
) -> None:
    """Run a benchmark over SWE-bench Lite. For each example, clone repo at given commit,
    run either the multi-agent graph (analysis→setup→planner→coder) or unified agent, and save per-example results.
    """
    try:
        # Set global context so any bare load_config() picks up CLI inputs
        overrides_dict = parse_config_overrides(config_overrides)
        set_global_config_context(config_file=config_file, overrides=overrides_dict or None)
        settings = setup_settings(workdir=workdir, require_github=True, config_file=config_file, config_overrides=config_overrides)
    except Exception:
        print("[red]Benchmark requires full env (GITHUB_TOKEN, REPO_URL irrelevant, GOOGLE_API_KEY).[/red]")
        raise typer.Exit(code=1)

    overrides_dict = parse_config_overrides(config_overrides)
    ds = load_dataset(subset, split=split)
    run_root = settings.workdir / "bench_runs" / subset.replace("/", "__") / split
    run_root.mkdir(parents=True, exist_ok=True)

    total = 0
    passed = 0
    runs = 0
    skipped_completed_count = 0
    skipped_repo_count = 0
    skipped_n_count = 0
    skipped_type_count = 0
    error_count = 0

    for i, ex in enumerate(ds):
        if limit is not None and runs >= limit:
            break
        if skip_n and i < skip_n:
            skipped_n_count += 1
            continue
        ex_id = ex.get("instance_id") or ex.get("_id") or f"idx-{i}"
        case_dir = run_root / str(ex_id)
        artifacts_dir = case_dir / "artifacts"
        repo_dir = case_dir / "repo"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        done_marker = artifacts_dir / "summary.json"
        if skip_completed and done_marker.exists():
            skipped_completed_count += 1
            continue
        if skip_repo:
            repo_url_val = str(ex.get("repo", ""))
            if skip_repo in repo_url_val:
                skipped_repo_count += 1
                continue

        runs += 1

        try:
            force_rmtree(case_dir)
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            repo_url = ex["repo"]
            log_panel("Bench", f"Cloning {repo_url} for {ex_id}")
            clone_repo(repo_url, repo_dir, github_token=settings.github_token, artifacts_dir=artifacts_dir)
            base_commit = ex.get("base_commit") or ex.get("base_sha")
            if base_commit:
                r = GitRepo(str(repo_dir))
                r.git.checkout(base_commit)
            test_patch_text = ex.get("test_patch") or ex.get("test_patch_str")
            test_files: list[str] = []
            if test_patch_text:
                test_files = _extract_test_files(test_patch_text)
                if apply_test_patch:
                    try:
                        r = GitRepo(str(repo_dir))
                        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".patch")
                        tmp.write(test_patch_text.encode("utf-8"))
                        tmp.flush()
                        tmp.close()
                        try:
                            r.git.apply(tmp.name, p=1, reject=True, whitespace="nowarn")
                        except Exception:
                            r.git.apply(tmp.name, p=0, reject=True, whitespace="nowarn")
                    except Exception as e:
                        write_file_text(str(artifacts_dir / "apply_test_patch_error.txt"), str(e))

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
                        settings, repo_dir, artifacts_dir, str(ex_id), dockerfile
                    )
                    pre_analysis = analysis
                else:
                    docker_info, pre_analysis = None, {}
        except Exception as e:
            write_file_text(str(artifacts_dir / "error.txt"), str(e))
            continue

        from .shared import create_execution_state
        issue_obj = GitHubIssue(number=0, title=str(ex.get("title", ex_id)), body=str(ex.get("problem_statement", "")), labels=["bench"])  # type: ignore
        bench_data = {
            "bench": {
                "id": ex_id,
                "type": _example_type(ex),
                "base_commit": base_commit,
                "test_files": test_files,
                "test_timeout": test_timeout,
            },
        }
        state = create_execution_state(
            settings=settings,
            issue=issue_obj,
            repo_dir=repo_dir,
            artifacts_dir=artifacts_dir,
            extra_data=bench_data,
            config_overrides=config_overrides,
            config_file=config_file,
        )
        try:
            early_issue_md = (
                f"# Issue\n\n**Title**: {str(ex.get('title', ex_id))}\n\n{str(ex.get('problem_statement', ''))}\n"
            )
            write_file_text(str(artifacts_dir / "issue.md"), early_issue_md)
        except Exception:
            pass
        if docker and docker_info:
            state["docker"] = docker_info
        if pre_analysis:
            state["analysis"] = pre_analysis
        et = state["bench"]["type"]
        if only_type != "all" and et != only_type:
            skipped_type_count += 1
            continue
        events: list = []
        try:
            state["events"] = events
            with LiveStatus(artifacts_dir=artifacts_dir) as live:
                state["live_update"] = live.update
                if unified:
                    live.update("[unified] Starting benchmark example...")
                    result = unified_agent_run(state)
                else:
                    graph = build_graph(max_loops=10)
                    live.update("[analysis] Starting benchmark example...")
                    result = graph.invoke(state)
        except Exception as e:
            write_file_text(str(artifacts_dir / "run_error.txt"), str(e))
            error_count += 1
            continue

        write_file_text(str(artifacts_dir / "analysis.json"), json.dumps(result.get("analysis", {}), indent=2))
        write_file_text(str(artifacts_dir / "plan.json"), json.dumps(result.get("plan", {}), indent=2))
        write_file_text(str(artifacts_dir / "transcript.json"), json.dumps(result.get("transcript", []), indent=2))
        write_file_text(str(artifacts_dir / "events.json"), json.dumps(events, indent=2))
        try:
            issue = state.get("issue")
            title = getattr(issue, "title", "")
            body = getattr(issue, "body", "")
            issue_md = f"# Issue\n\n**Title**: {title}\n\n{body}\n"
            write_file_text(str(artifacts_dir / "issue.md"), issue_md)
        except Exception:
            pass

        total += 1
        done = bool(result.get("iteration", {}).get("done"))
        if done:
            passed += 1
        solved = None
        test_exit = None
        try:
            tests = state["bench"].get("test_files", []) or []
            if tests:
                cmd = "python -m pytest -q " + " ".join(tests)
                if docker and docker_info:
                    config = load_config(config_file=config_file, overrides=overrides_dict)
                    workdir = docker_info.get("workdir", config.docker.get("workspace_dir", "/workspace"))
                    container_id = docker_info.get("container_id")
                    test_cmd = f"docker exec -w {workdir} {container_id} sh -lc \"{cmd}\""
                    code, out, err = run_shell(test_cmd, cwd=str(repo_dir), timeout=test_timeout)
                else:
                    code, out, err = run_shell(cmd, cwd=str(repo_dir), timeout=test_timeout)
                test_exit = code
                solved = (code == 0)
        except Exception:
            pass

        summary = {
            "status": "success" if done else "incomplete",
            "commit_message": result.get("iteration", {}).get("commit_message"),
            "type": et,
            "tests": state["bench"].get("test_files", []),
            "solved": solved,
            "test_exit_code": test_exit,
        }
        write_file_text(str(artifacts_dir / "summary.json"), json.dumps(summary, indent=2))

        if docker and docker_info and docker_info.get("container_id"):
            try:
                run_shell(f"docker rm -f {docker_info['container_id']}")
            except Exception:
                pass

    incomplete = total - passed
    bench_summary = {
        "runs": runs,
        "processed": total,
        "passed": passed,
        "incomplete": incomplete,
        "skipped": {
            "completed": skipped_completed_count,
            "repo": skipped_repo_count,
            "initial": skipped_n_count,
            "type": skipped_type_count,
        },
        "errors": error_count,
    }
    try:
        write_file_text(str(run_root / "summary.json"), json.dumps(bench_summary, indent=2))
    except Exception:
        pass
    print(f"[green]Benchmark completed[/green]: runs={runs}, passed={passed}, incomplete={incomplete}, skipped={skipped_completed_count+skipped_repo_count+skipped_n_count+skipped_type_count}, errors={error_count}")
