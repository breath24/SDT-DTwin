from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple

import typer
from rich import print
from dotenv import load_dotenv

from .config import Settings
from .github_client import GitHubClient
from .tools import clone_repo, create_branch_commit_push, write_file_text
from .graph import build_graph
from .github_client import GitHubIssue
from .utils.logging import LiveStatus, log_panel, write_status_line
from .utils.fs_extra import force_rmtree
from datasets import load_dataset
from .tools.shell import run_shell, run_shell_stream
from .agents.analysis import analysis_node


app = typer.Typer(add_completion=False)
bench = typer.Typer(add_completion=False)
demo = typer.Typer(add_completion=False)
app.add_typer(bench, name="bench")
app.add_typer(demo, name="demo")


def _parse_branch_name(issue_number: int, title: str) -> str:
    slug = "-".join(title.lower().split())[:40]
    unique = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    return f"dev-twin/issue-{issue_number}-{slug}-{unique}"


def _ensure_docker_container(
    settings: Settings,
    repo_dir: Path,
    artifacts_dir: Path,
    tag_hint: str,
) -> Tuple[Optional[dict], dict]:
    docker_info: Optional[dict] = None
    analysis: dict = {}
    try:
        pre_state = {
            "settings": settings,
            "repo_dir": repo_dir,
            "transcript": [],
            "artifacts_dir": artifacts_dir,
            "events": [],
        }
        write_status_line(artifacts_dir, "[docker] Pre-analysis to generate Dockerfile...")
        pre_state = analysis_node(pre_state)
        analysis = pre_state.get("analysis", {}) or {}
        dockerfile = analysis.get("dockerfile_suggested")
        if dockerfile:
            docker_path = artifacts_dir / "Dockerfile"
            write_file_text(str(docker_path), dockerfile)
            write_status_line(artifacts_dir, "[docker] Building image...")
            safe_tag = ("devtwin-" + tag_hint).lower().replace("/", "-").replace("__", "-")
            build_cmd = f"docker build -t {safe_tag} -f {docker_path} {repo_dir}"
            def _on_build(line: str) -> None:
                # Stream build lines periodically
                if line:
                    write_status_line(artifacts_dir, f"[docker][build] {line}")
            code, combined = run_shell_stream(build_cmd, on_line=_on_build)
            if code == 0:
                write_status_line(artifacts_dir, "[docker] Starting container...")
                abs_repo = str(repo_dir.resolve())
                run_cmd = f"docker run -d -v \"{abs_repo}\":/workspace -w /workspace {safe_tag} sleep infinity"
                # Stream first line with container id
                code, combined = run_shell_stream(run_cmd)
                if code == 0:
                    container_id = (combined or "").strip()
                    docker_info = {"container_id": container_id, "workdir": "/workspace"}
                else:
                    write_file_text(str(artifacts_dir / "docker_run_error.txt"), combined)
            else:
                write_file_text(str(artifacts_dir / "docker_build_error.txt"), combined)
    except Exception as e:
        write_file_text(str(artifacts_dir / "docker_error.txt"), str(e))
    return docker_info, analysis


def _project_root() -> Path:
    # src/ is one level below project root
    return Path(__file__).resolve().parents[1]


def _read_issue_file(issue_path: Path) -> tuple[str, str]:
    text = issue_path.read_text(encoding="utf-8") if issue_path.exists() else ""
    lines = [ln.strip() for ln in text.splitlines()]
    title = "Demo Issue"
    body_lines: list[str] = []
    for i, ln in enumerate(lines):
        if ln:
            title = ln.lstrip("# ").strip()
            body_lines = lines[i + 1 :]
            break
    body = "\n".join(body_lines).strip()
    return title, body


def _read_issue_file(issue_path: Path) -> tuple[str, str]:
    text = issue_path.read_text(encoding="utf-8") if issue_path.exists() else ""
    lines = [ln.strip() for ln in text.splitlines()]
    title = "Demo Issue"
    body_lines: list[str] = []
    for i, ln in enumerate(lines):
        if ln:
            title = ln.lstrip("# ").strip()
            body_lines = lines[i + 1 :]
            break
    body = "\n".join(body_lines).strip()
    return title, body
@app.command()
def main(
    issue: Optional[int] = typer.Option(None),
    workdir: Optional[str] = typer.Option(None),
    docker: bool = typer.Option(False, help="Run inside Docker using analysis-suggested Dockerfile"),
) -> None:
    try:
        load_dotenv()
        settings = Settings.from_env()
        if workdir:
            settings.workdir = Path(workdir)
        local_mode = False
        try:
            settings.ensure()
        except Exception as e:
            print(f"[yellow]Missing env for remote run ({e}). Falling back to local dry-run.[/yellow]")
            local_mode = True

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
            # Clear old workspace for this issue to ensure fresh runs (entire issue folder)
            force_rmtree(issue_root)
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            # Clone with token so origin is accessible
            # Log the exact clone target
            pretty_path = str(repo_dir).replace("\\", "/")
            log_panel("Clone", f"Cloning into: {pretty_path}\nURL: {settings.repo_url}")
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
            write_file_text(str(repo_dir / "README.md"), "# Sample Repo\n\nThis is a local dry-run.")
            gh_issue = GitHubIssue(number=0, title="Local dry run", body="No GitHub configured", labels=["dev-twin"])  # type: ignore

        # Optionally create Dockerfile if suggested later
        state = {
            "settings": settings,
            "issue": gh_issue,
            "repo_dir": repo_dir,
            "transcript": [],
            "artifacts_dir": artifacts_dir,
        }

        # If docker requested (and not in local dry-run), pre-run analysis to obtain Dockerfile, then build & start container
        docker_info = None
        pre_analysis: dict = {}
        if docker and not local_mode:
            docker_info, pre_analysis = _ensure_docker_container(
                settings, repo_dir, artifacts_dir, tag_hint=("main-" + gh.repo_full_name.replace("/", "__"))
            )

        # If local_mode is set (missing required env), do a dry-run result without LLM
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
                graph = build_graph(max_loops=10)
                # Inject simple callbacks into state so nodes can update status and log events
                state["live_update"] = live.update
                state["events"] = events
                if docker_info:
                    state["docker"] = docker_info
                if pre_analysis:
                    state["analysis"] = pre_analysis
                result = graph.invoke(state)
            live.update("Writing artifacts...")
            # Save artifacts
            write_file_text(str(artifacts_dir / "analysis.json"), json.dumps(result.get("analysis", {}), indent=2))
            write_file_text(str(artifacts_dir / "plan.json"), json.dumps(result.get("plan", {}), indent=2))
            write_file_text(str(artifacts_dir / "transcript.json"), json.dumps(result.get("transcript", []), indent=2))
            write_file_text(str(artifacts_dir / "events.json"), json.dumps(events, indent=2))
            # Export notes (if any) into a human-friendly file
            try:
                notes_log = artifacts_dir / ".devtwin_notes.jsonl"
                if notes_log.exists():
                    lines_md = []
                    for raw in notes_log.read_text(encoding="utf-8").splitlines():
                        import json as _json
                        try:
                            obj = _json.loads(raw)
                            lines_md.append(f"- [{obj.get('ts')}] **{obj.get('topic')}**: {obj.get('content')}")
                        except Exception:
                            continue
                    write_file_text(str(artifacts_dir / "notes.md"), "\n".join(lines_md) or "(no notes)")
            except Exception:
                pass
            # If a clone error marker exists, capture it into artifacts
            try:
                marker = repo_dir.parent / "clone_error.txt"
                if marker.exists():
                    write_file_text(str(artifacts_dir / "clone_error.txt"), marker.read_text(encoding="utf-8"))
            except Exception:
                pass

        # If analysis suggested a Dockerfile, write it into artifacts (best-effort)
        analysis = result.get("analysis", {})
        dockerfile = analysis.get("dockerfile_suggested")
        if dockerfile:
            try:
                docker_path = artifacts_dir / "Dockerfile"
                write_file_text(str(docker_path), dockerfile)
                print("[green]Dockerfile generated under artifacts.[/green]")
            except Exception as e:
                print(f"[yellow]Failed to write Dockerfile: {e}[/yellow]")

        # When done, open PR
        iteration = result.get("iteration")
        if iteration and iteration.get("done"):
            branch = _parse_branch_name(gh_issue.number, gh_issue.title)
            if not local_mode:
                # Build a concise PR body summary (instead of dumping transcript)
                tests_ran = any(
                    "pytest" in e.get("args", {}).get("command", "") or "npm test" in e.get("args", {}).get("command", "")
                    for e in events if e.get("tool") == "shell"
                )
                plan_steps = result.get("plan", {}).get("steps", [])
                step_lines = [f"- {s.get('description')}" for s in plan_steps[:5] if s.get("description")]
                plan_section = ("\n".join(step_lines)) if step_lines else "- (no plan steps)"
                pr_body = (
                    "Automated edits by Developer Twin.\n\n"
                    f"Summary:\n- Commit: {iteration.get('commit_message')}\n- Tests ran: {'yes' if tests_ran else 'no'}\n- Notes: see artifacts/notes.md\n\n"
                    f"Plan:\n{plan_section}"
                )
                create_branch_commit_push(
                    repo_dir,
                    branch,
                    iteration.get("commit_message", "dev-twin changes"),
                    github_token=settings.github_token,
                    repo_url=settings.repo_url,
                )
                pr_title = f"dev-twin: {gh_issue.title}"
                # Use repo default branch when creating PR
                try:
                    default_base = gh._repo.default_branch  # type: ignore[attr-defined]
                except Exception:
                    default_base = "main"
                pr_url = gh.create_pull_request(head=branch, base=default_base, title=pr_title, body=pr_body)
                print(f"[green]Created PR:[/green] {pr_url}")
            else:
                print(f"[green]Dry run complete. Would have created PR with commit '{iteration.get('commit_message')}'.[/green]")
            # Summary
            summary = {
                "status": "success",
                "commit_message": iteration.get("commit_message"),
                "pr_url": pr_url if not local_mode else None,
                "tests_ran": any("pytest" in e.get("args", {}).get("command", "") or "npm test" in e.get("args", {}).get("command", "") for e in events if e.get("tool") == "shell"),
            }
            write_file_text(str(artifacts_dir / "summary.json"), json.dumps(summary, indent=2))
            # Export notes (if any) into a human-friendly file
            notes_log = repo_dir.parent / "artifacts" / ".devtwin_notes.jsonl"
            if notes_log.exists():
                try:
                    # Convert to a simple Markdown list for quick viewing
                    lines = []
                    for raw in notes_log.read_text(encoding="utf-8").splitlines():
                        import json as _json
                        try:
                            obj = _json.loads(raw)
                            lines.append(f"- [{obj.get('ts')}] **{obj.get('topic')}**: {obj.get('content')}")
                        except Exception:
                            continue
                    write_file_text(str(artifacts_dir / "notes.md"), "\n".join(lines) or "(no notes)")
                except Exception:
                    pass
            # Log summary to CLI and write a summary.md under artifacts
            log_panel("Run Summary", json.dumps(summary, indent=2))
            try:
                write_file_text(str(artifacts_dir / "summary.md"), f"Run summary\n\n- status: {summary['status']}\n- commit: {summary['commit_message']}\n- tests_ran: {'yes' if summary.get('tests_ran') else 'no'}\n")
            except Exception:
                pass
        else:
            # Emit an explicit end-of-run marker with last note or error hint
            try:
                last_event = events[-1] if events else {}
                hint = last_event.get("result") or last_event.get("tool") or "no events"
            except Exception:
                hint = "unknown"
            print("[yellow]Graph ended without 'done': true. Review transcript for progress.[/yellow]")
            write_file_text(str(artifacts_dir / "end_marker.txt"), f"Graph ended without done. Last hint: {hint}")
        log_panel("Artifacts", f"Saved to: {artifacts_dir}")
        # Cleanup Docker container if created
        if docker_info and docker_info.get("container_id"):
            try:
                run_shell(f"docker rm -f {docker_info['container_id']}")
            except Exception:
                pass
    except Exception as e:
        print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


@demo.command("run")
def demo_run(
    name: Optional[str] = typer.Option(None, help="Specific demo project to run (default: all)"),
    workdir: Optional[str] = typer.Option(None, help="Override workdir for artifacts (defaults under demo dir)"),
    docker: bool = typer.Option(False, help="Run inside Docker using analysis-suggested Dockerfile"),
) -> None:
    """Run the agent on one or all demo projects in `demos/`."""
    load_dotenv()
    settings = Settings.from_env()
    if workdir:
        settings.workdir = Path(workdir)
    try:
        # For demo mode, require a valid provider and corresponding API key,
        # but not necessarily GitHub or repo URL
        valid_providers = ["google", "openai", "anthropic", "openrouter"]
        if settings.provider not in valid_providers:
            raise ValueError(f"Invalid PROVIDER: {settings.provider}. Choose one of: {', '.join(valid_providers)}")
        api_key = settings.get_current_api_key()
        if not api_key:
            raise ValueError(f"{settings.provider.upper()}_API_KEY is required for demo run when PROVIDER={settings.provider}")
        settings.workdir.mkdir(parents=True, exist_ok=True)
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

    for demo_name in demo_names:
        # Source (committed) demo
        src_case = demos_dir / demo_name
        src_repo = src_case / "repo"
        src_issue = src_case / "issue.md"

        # Destination (ephemeral) workspace copy under workdir
        case_dir = settings.workdir / "demos" / demo_name
        repo_dir = case_dir / "repo"
        artifacts_dir = case_dir / "artifacts"
        # Reset the demo workspace so every run starts clean
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
            docker_info, pre_analysis = _ensure_docker_container(
                settings, repo_dir, artifacts_dir, tag_hint=f"demo-{demo_name}"
            )

        state = {
            "settings": settings,
            "issue": issue_obj,
            "repo_dir": repo_dir,
            "transcript": [],
            "artifacts_dir": artifacts_dir,
        }
        events: list = []
        try:
            graph = build_graph(max_loops=10)
            state["events"] = events
            if docker_info:
                state["docker"] = docker_info
            if pre_analysis:
                state["analysis"] = pre_analysis
            with LiveStatus(artifacts_dir=artifacts_dir) as live:
                state["live_update"] = live.update
                live.update(f"[analysis] Running demo: {demo_name}...")
                result = graph.invoke(state) if demo_has_llm else {
                    "analysis": {"project_type": "unknown", "build_commands": [], "test_commands": [], "run_commands": []},
                    "plan": {"steps": [{"id": "noop", "description": "No-op in demo dry run", "rationale": "No API key"}]},
                    "iteration": {"actions": [], "commit_message": "dev-twin demo dry run", "done": True},
                    "transcript": state["transcript"],
                }
        except Exception as e:
            write_file_text(str(artifacts_dir / "run_error.txt"), str(e))
            continue

        # Save artifacts
        write_file_text(str(artifacts_dir / "analysis.json"), json.dumps(result.get("analysis", {}), indent=2))
        write_file_text(str(artifacts_dir / "plan.json"), json.dumps(result.get("plan", {}), indent=2))
        write_file_text(str(artifacts_dir / "transcript.json"), json.dumps(result.get("transcript", []), indent=2))
        write_file_text(str(artifacts_dir / "events.json"), json.dumps(events, indent=2))

        iteration = result.get("iteration", {})
        summary = {
            "status": "success" if iteration.get("done") else "incomplete",
            "commit_message": iteration.get("commit_message"),
            "demo": demo_name,
        }
        write_file_text(str(artifacts_dir / "summary.json"), json.dumps(summary, indent=2))
        # Also log a concise summary to CLI and write summary.md
        try:
            log_panel("Run Summary", json.dumps(summary, indent=2))
            write_file_text(
                str(artifacts_dir / "summary.md"),
                f"Run summary (demo: {demo_name})\n\n- status: {summary['status']}\n- commit: {summary['commit_message']}\n",
            )
        except Exception:
            pass

        # Cleanup container
        if docker and docker_info and docker_info.get("container_id"):
            try:
                run_shell(f"docker rm -f {docker_info['container_id']}")
            except Exception:
                pass
@bench.command("run")
def bench_run(
    subset: str = typer.Option("princeton-nlp/SWE-bench_Lite", help="HF dataset path"),
    split: str = typer.Option("test", help="Dataset split"),
    limit: Optional[int] = typer.Option(None, help="Limit number of examples"),
    workdir: Optional[str] = typer.Option(None, help="Override workdir"),
    skip_completed: bool = typer.Option(True, help="Skip examples already completed"),
    skip_n: int = typer.Option(0, help="Skip the first N examples in the split"),
    skip_repo: Optional[str] = typer.Option(None, help="Skip all examples whose repo contains this substring (e.g., 'astropy/astropy')"),
    only_type: str = typer.Option("fail", help="Filter by type: 'fail', 'pass', or 'all'"),
    apply_test_patch: bool = typer.Option(True, help="Apply test_patch to add failing tests before running"),
    test_timeout: int = typer.Option(120, help="Timeout in seconds for individual test runs"),
    docker: bool = typer.Option(False, help="Run inside Docker using analysis-suggested Dockerfile"),
):
    """Run a benchmark over SWE-bench Lite. For each example, clone repo at given commit,
    run the same graph (analysis→setup→planner→coder), and save per-example results.
    """
    load_dotenv()
    settings = Settings.from_env()
    if workdir:
        settings.workdir = Path(workdir)
    try:
        settings.ensure()
    except Exception:
        print("[red]Benchmark requires full env (GITHUB_TOKEN, REPO_URL irrelevant, GOOGLE_API_KEY).[/red]")
        raise typer.Exit(code=1)

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

    def _example_type(e: dict) -> str:
        # Flexible detection across variants
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

    def _extract_test_files(patch_text: str) -> list[str]:
        files: list[str] = []
        for line in patch_text.splitlines():
            if line.startswith("+++ b/"):
                path = line[6:].strip()
                if path and ("test" in path or path.startswith("tests/")):
                    files.append(path)
        # dedupe
        return sorted(set(files))

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

        # This example will be processed as a run
        runs += 1

        # Prepare repo
        try:
            force_rmtree(case_dir)
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            repo_url = ex["repo"]
            # Clone
            log_panel("Bench", f"Cloning {repo_url} for {ex_id}")
            clone_repo(repo_url, repo_dir, github_token=settings.github_token, artifacts_dir=artifacts_dir)
            # Checkout to the specified base commit if present
            base_commit = ex.get("base_commit") or ex.get("base_sha")
            if base_commit:
                from git import Repo as _Repo
                r = _Repo(str(repo_dir))
                r.git.checkout(base_commit)
            # Optionally apply test_patch to add failing tests
            test_patch_text = ex.get("test_patch") or ex.get("test_patch_str")
            test_files: list[str] = []
            if test_patch_text:
                test_files = _extract_test_files(test_patch_text)
                if apply_test_patch:
                    try:
                        from git import Repo as _Repo
                        r = _Repo(str(repo_dir))
                        # write temp patch
                        import tempfile
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

            # If docker is requested, pre-run analysis to get a Dockerfile, then build & start a container
            docker_info = None
            pre_analysis: dict = {}
            if docker:
                docker_info, pre_analysis = _ensure_docker_container(
                    settings, repo_dir, artifacts_dir, tag_hint=str(ex_id)
                )
        except Exception as e:
            write_file_text(str(artifacts_dir / "error.txt"), str(e))
            continue

        # Build state and run graph with live status to mirror normal run
        state = {
            "settings": settings,
            "issue": GitHubIssue(number=0, title=str(ex.get("title", ex_id)), body=str(ex.get("problem_statement", "")), labels=["bench"]),  # type: ignore
            "repo_dir": repo_dir,
            "transcript": [],
            "artifacts_dir": artifacts_dir,
            "bench": {
                "id": ex_id,
                "type": _example_type(ex),
                "base_commit": base_commit,
                "test_files": test_files,
                "test_timeout": test_timeout,
            },
        }
        if docker and docker_info:
            state["docker"] = docker_info
        if pre_analysis:
            state["analysis"] = pre_analysis
        # Filter by type
        et = state["bench"]["type"]
        if only_type != "all" and et != only_type:
            skipped_type_count += 1
            continue
        events: list = []
        try:
            graph = build_graph(max_loops=10)
            state["events"] = events
            from .utils.logging import LiveStatus
            with LiveStatus(artifacts_dir=artifacts_dir) as live:
                state["live_update"] = live.update
                live.update("[analysis] Starting benchmark example...")
                result = graph.invoke(state)
        except Exception as e:
            write_file_text(str(artifacts_dir / "run_error.txt"), str(e))
            error_count += 1
            continue

        # Save artifacts
        write_file_text(str(artifacts_dir / "analysis.json"), json.dumps(result.get("analysis", {}), indent=2))
        write_file_text(str(artifacts_dir / "plan.json"), json.dumps(result.get("plan", {}), indent=2))
        write_file_text(str(artifacts_dir / "transcript.json"), json.dumps(result.get("transcript", []), indent=2))
        write_file_text(str(artifacts_dir / "events.json"), json.dumps(events, indent=2))

        # Optional post-run targeted test validation
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
                    workdir = docker_info.get("workdir", "/workspace")
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

        # Cleanup Docker container
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


if __name__ == "__main__":
    app()


