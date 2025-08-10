from __future__ import annotations

from typing import Optional, List

import typer

from .cli.main_handler import handle_main_command  
from .cli.demo_commands import demo_run
from .cli.bench_commands import bench_run


app = typer.Typer(add_completion=False)
bench = typer.Typer(add_completion=False)
demo = typer.Typer(add_completion=False)
app.add_typer(bench, name="bench")
app.add_typer(demo, name="demo")


@app.command()
def main(
    issue: Optional[int] = typer.Option(None),
    workdir: Optional[str] = typer.Option(None),
    docker: bool = typer.Option(False, help="Run inside Docker using analysis-suggested Dockerfile"),
    multi_agent: bool = typer.Option(False, help="Use multi-agent workflow instead of the default unified agent"),
    config_file: Optional[str] = typer.Option(None, help="Path to custom configuration file"),
    config: Optional[List[str]] = typer.Option(None, help="Configuration overrides in key=value format (e.g., --config agents.unified.max_steps=300)"),
) -> None:
    """Main dev-twin command - now using refactored modular code."""
    handle_main_command(
        issue=issue, 
        workdir=workdir, 
        docker=docker, 
        unified=not multi_agent,
        config_file=config_file,
        config_overrides=config
    )


@demo.command("run")
def demo_run_command(
    name: Optional[str] = typer.Option(None, help="Specific demo project to run (default: all)"),
    workdir: Optional[str] = typer.Option(None, help="Override workdir for artifacts (defaults under demo dir)"),
    docker: bool = typer.Option(False, help="Run inside Docker using analysis-suggested Dockerfile"),
    multi_agent: bool = typer.Option(False, help="Use multi-agent workflow instead of the default unified agent"),
    bench: bool = typer.Option(False, help="Aggregate pass/fail and output a summary across demos"),
    config_file: Optional[str] = typer.Option(None, help="Path to custom configuration file"),
    config: Optional[List[str]] = typer.Option(None, help="Configuration overrides in key=value format"),
) -> None:
    """Run the agent on one or all demo projects in `demos/`."""
    demo_run(
        name=name, 
        workdir=workdir, 
        docker=docker, 
        unified=not multi_agent, 
        bench=bench,
        config_file=config_file,
        config_overrides=config
    )

@bench.command("run")
def bench_run_command(
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
    multi_agent: bool = typer.Option(False, help="Use multi-agent workflow instead of the default unified agent"),
    config_file: Optional[str] = typer.Option(None, help="Path to custom configuration file"),
    config: Optional[List[str]] = typer.Option(None, help="Configuration overrides in key=value format"),
):
    """Run a benchmark over SWE-bench Lite."""
    bench_run(
        subset=subset, split=split, limit=limit, workdir=workdir, 
        skip_completed=skip_completed, skip_n=skip_n, skip_repo=skip_repo,
        only_type=only_type, apply_test_patch=apply_test_patch, 
        test_timeout=test_timeout, docker=docker, unified=not multi_agent,
        config_file=config_file, config_overrides=config
    )


if __name__ == "__main__":
    app()


