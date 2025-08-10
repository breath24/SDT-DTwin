"""Docker container management for development environments."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .config_loader import load_config
from .tools.shell import run_shell, run_shell_stream
from .tools.fs import write_file_text
from .utils.logging import write_status_line


class DockerManager:
    """Manages Docker containers for isolated development environments."""

    def __init__(self, artifacts_dir: Path):
        self.artifacts_dir = artifacts_dir

    def build_and_start_container(
        self,
        dockerfile_content: str,
        repo_dir: Path,
        tag_hint: str,
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        """
        Build and start a Docker container for the project.
        
        Returns:
            Tuple of (docker_info, build_logs) where docker_info contains
            container_id and workdir if successful, None otherwise.
        """
        build_logs: Dict[str, Any] = {}
        docker_info: Optional[Dict[str, Any]] = None

        try:
            # Write Dockerfile
            docker_path = self.artifacts_dir / "Dockerfile"
            write_file_text(str(docker_path), dockerfile_content)
            
            # Build image
            safe_tag = self._create_safe_tag(tag_hint)
            write_status_line(self.artifacts_dir, "[docker] Building image...")
            
            build_cmd = f"docker build -t {safe_tag} -f {docker_path} {repo_dir}"
            build_logs["build_command"] = build_cmd
            
            code, combined = run_shell_stream(
                build_cmd, 
                on_line=lambda line: self._on_build_line(line) if line else None
            )
            
            build_logs["build_exit_code"] = code
            build_logs["build_output"] = combined
            
            if code == 0:
                docker_info = self._start_container(safe_tag, repo_dir, build_logs)
            else:
                write_file_text(
                    str(self.artifacts_dir / "docker_build_error.txt"), 
                    combined or ""
                )
                
        except Exception as e:
            build_logs["error"] = str(e)
            write_file_text(
                str(self.artifacts_dir / "docker_error.txt"), 
                str(e)
            )

        return docker_info, build_logs

    def _create_safe_tag(self, tag_hint: str) -> str:
        """Create a safe Docker tag from hint."""
        return ("devtwin-" + tag_hint).lower().replace("/", "-").replace("__", "-")

    def _on_build_line(self, line: str) -> None:
        """Handle Docker build output line."""
        write_status_line(self.artifacts_dir, f"[docker][build] {line}")

    def _start_container(
        self, 
        tag: str, 
        repo_dir: Path, 
        build_logs: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Start the Docker container."""
        try:
            write_status_line(self.artifacts_dir, "[docker] Starting container...")
            
            abs_repo = str(repo_dir.resolve())
            config = load_config()
            workspace_dir = config.docker.get("workspace_dir", "/workspace")
            sleep_cmd = config.docker.get("sleep_cmd", "sleep infinity")
            
            run_cmd = (
                f'docker run -d -v "{abs_repo}":{workspace_dir} '
                f'-w {workspace_dir} {tag} {sleep_cmd}'
            )
            
            build_logs["run_command"] = run_cmd
            code, combined = run_shell_stream(run_cmd)
            build_logs["run_exit_code"] = code
            build_logs["run_output"] = combined
            
            if code == 0:
                container_id = (combined or "").strip()
                return {
                    "container_id": container_id,
                    "workdir": workspace_dir
                }
            else:
                write_file_text(
                    str(self.artifacts_dir / "docker_run_error.txt"), 
                    combined or ""
                )
                return None
                
        except Exception as e:
            build_logs["run_error"] = str(e)
            return None

    @staticmethod
    def cleanup_container(container_id: str) -> None:
        """Clean up a Docker container."""
        try:
            run_shell(f"docker rm -f {container_id}")
        except Exception:
            # Best effort cleanup
            pass

    def apply_test_patch(self, patch_content: str, repo_dir: Path) -> bool:
        """Apply a test patch to the repository."""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".patch") as tmp:
                tmp.write(patch_content.encode("utf-8"))
                tmp.flush()
                
                from git import Repo
                repo = Repo(str(repo_dir))
                
                try:
                    repo.git.apply(tmp.name, p=1, reject=True, whitespace="nowarn")
                    return True
                except Exception:
                    # Try with different patch level
                    repo.git.apply(tmp.name, p=0, reject=True, whitespace="nowarn")
                    return True
                    
        except Exception as e:
            write_file_text(
                str(self.artifacts_dir / "apply_test_patch_error.txt"), 
                str(e)
            )
            return False


def ensure_docker_environment(
    settings,
    repo_dir: Path,
    artifacts_dir: Path,
    tag_hint: str,
    dockerfile_content: str,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    Convenience function to ensure a Docker environment is ready.
    
    This is the main entry point for Docker functionality.
    """
    manager = DockerManager(artifacts_dir)
    return manager.build_and_start_container(dockerfile_content, repo_dir, tag_hint)
