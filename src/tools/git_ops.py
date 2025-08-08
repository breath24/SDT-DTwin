from __future__ import annotations

from pathlib import Path
from typing import Optional

from git import Repo
from ..utils.git_url import with_token, to_https_url
from ..utils.fs_extra import force_rmtree
import shutil
import subprocess
import os


def _verify_repo_checkout(dest_dir: Path) -> bool:
    try:
        git_dir = dest_dir / ".git"
        if not git_dir.exists():
            return False
        # any tracked files present
        for _ in dest_dir.rglob("*"):
            return True
    except Exception:
        return False
    return False


def _clone_with_system_git(url: str, dest_dir: Path) -> None:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = "echo"
    subprocess.check_call(["git", "clone", url, str(dest_dir)], env=env)


def clone_repo(repo_url: str, dest_dir: Path, github_token: str | None = None, artifacts_dir: Path | None = None) -> Path:
    # If target directory exists (even empty), remove it to avoid clone no-op
    if dest_dir.exists():
        force_rmtree(dest_dir)
    # Normalize owner/repo to https first, then add token if provided
    url = with_token(to_https_url(repo_url), github_token)
    try:
        # Ensure parent exists and is writable
        dest_dir.parent.mkdir(parents=True, exist_ok=True)
        # Prefer system git for reliability; fallback to GitPython
        try:
            _clone_with_system_git(url, dest_dir)
        except Exception:
            Repo.clone_from(url, dest_dir)
        # Write a marker that clone succeeded (if it did)
        if _verify_repo_checkout(dest_dir):
            marker_dir = artifacts_dir if artifacts_dir else dest_dir.parent
            try:
                (marker_dir / ".cloned").write_text("ok", encoding="utf-8")
            except Exception:
                pass
        else:
            raise RuntimeError("clone appeared to succeed but repo is empty or missing .git")
    except Exception as e:
        # Write a failure marker file into dest_dir parent for debugging
        try:
            marker_dir = artifacts_dir if artifacts_dir else dest_dir.parent
            (marker_dir / "clone_error.txt").write_text(f"{e}\nURL={url}", encoding="utf-8")
        except Exception:
            pass
        raise
    return dest_dir


def create_branch_commit_push(
    repo_path: Path,
    branch_name: str,
    commit_message: str,
    remote_name: str = "origin",
    github_token: str | None = None,
    repo_url: str | None = None,
) -> None:
    repo = Repo(str(repo_path))
    if branch_name not in repo.heads:
        repo.git.checkout("-b", branch_name)
    else:
        repo.git.checkout(branch_name)
    if repo.is_dirty(untracked_files=True):
        repo.git.add(all=True)
        repo.index.commit(commit_message)
    # Push and set upstream
    original_url = None
    try:
        remote = repo.remotes[remote_name]
        original_url = remote.url
    except Exception:
        remote = repo.create_remote(remote_name, url=repo_url or "")
        original_url = remote.url

    # If token provided and repo_url is https, set push URL temporarily
    temp_set = False
    if github_token and (repo_url or original_url):
        url = (repo_url or original_url)
        if url.startswith("https://") and "@" not in url:
            token_url = url.replace("https://", f"https://{github_token}@")
            try:
                repo.git.remote("set-url", "--push", remote_name, token_url)
                temp_set = True
            except Exception:
                pass

    repo.git.push("-u", remote_name, branch_name)

    # restore push URL
    if temp_set and original_url:
        try:
            repo.git.remote("set-url", "--push", remote_name, original_url)
        except Exception:
            pass


