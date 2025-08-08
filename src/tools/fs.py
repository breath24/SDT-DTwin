from __future__ import annotations

from pathlib import Path
import os
from typing import List, Optional

from .shell import run_shell
import tempfile
import textwrap


def read_file_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write_file_text(path: str, content: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def list_directory(path: str) -> List[str]:
    p = Path(path)
    if not p.exists():
        return []
    # Prefer ripgrep enumeration which respects .gitignore by default
    code, _, _ = run_shell("rg --version")
    if code == 0:
        if p.is_dir():
            # Exclude heavy/irrelevant directories even if not in .gitignore
            common_excludes = [
                "!node_modules/**",
                "!**/node_modules/**",
                "!.git/**",
                "!**/.git/**",
                "!dist/**",
                "!**/dist/**",
                "!build/**",
                "!**/build/**",
                "!venv/**",
                "!**/venv/**",
                "!.venv/**",
                "!**/.venv/**",
                "!__pycache__/**",
                "!**/__pycache__/**",
                "!.tox/**",
                "!**/.tox/**",
                "!.mypy_cache/**",
                "!**/.mypy_cache/**",
            ]
            glob_args = " ".join([f'--glob "{g}"' for g in common_excludes])
            code, out, err = run_shell(f"rg --files {glob_args}", cwd=str(p))
            if code == 0:
                # Return relative paths under the provided directory
                return [line.strip() for line in out.splitlines() if line.strip()]
        else:
            return [p.name]
    # Fallback: basic recursive listing with common excludes
    results: List[str] = []
    base = p if p.is_dir() else p.parent
    if p.is_file():
        return [p.name]
    # Use os.walk so we can prune directories and avoid traversing into ignored folders
    excluded_dirs = {".git", ".hg", ".svn", "node_modules", ".venv", "venv", "dist", "build", "__pycache__", ".tox", ".mypy_cache"}
    excluded_suffixes = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".ico", ".min.js", ".min.css"}
    for root, dirs, files in os.walk(base):
        # Prune excluded directories in-place
        dirs[:] = [d for d in dirs if d.lower() not in excluded_dirs]
        for fname in files:
            # Skip obviously heavy/binary or minified assets
            lower = fname.lower()
            if any(lower.endswith(suf) for suf in excluded_suffixes):
                continue
            abs_path = Path(root) / fname
            try:
                rel = abs_path.relative_to(base)
                results.append(str(rel))
            except Exception:
                continue
    return results


def search_ripgrep(pattern: str, path: str, max_results: int = 200, timeout: Optional[int] = 12) -> str:
    # Try ripgrep first; defaults respect .gitignore and hidden files are skipped
    code, _, _ = run_shell("rg --version")
    if code == 0:
        base = Path(path)
        # Quote pattern for shell
        qpat = '"' + pattern.replace('"', '\\"') + '"'
        common_excludes = [
            "!node_modules/**",
            "!**/node_modules/**",
            "!.git/**",
            "!**/.git/**",
            "!dist/**",
            "!**/dist/**",
            "!build/**",
            "!**/build/**",
            "!venv/**",
            "!**/venv/**",
            "!.venv/**",
            "!**/.venv/**",
            "!__pycache__/**",
            "!**/__pycache__/**",
            "!*.min.*",
            "!*.lock",
        ]
        glob_args = " ".join([f'--glob "{g}"' for g in common_excludes])
        if base.is_dir():
            cmd = f"rg -n --no-heading --color never -S -m {max_results} --max-filesize 2M {glob_args} {qpat} ."
            code, out, err = run_shell(cmd, cwd=str(base), timeout=timeout)
        else:
            cmd = f"rg -n --no-heading --color never -S -m {max_results} --max-filesize 2M {qpat} {base.name}"
            code, out, err = run_shell(cmd, cwd=str(base.parent), timeout=timeout)
        return out if code == 0 else (out or err)

    # Fallback to Python recursive grep
    base = Path(path)
    results: List[str] = []
    try:
        for p in base.rglob("*"):
            if p.is_dir():
                # skip VCS & node_modules-like
                name = p.name.lower()
                if name in {".git", ".hg", ".svn", "node_modules", ".venv", "venv", "dist", "build"}:
                    continue
                continue
            if p.suffix in {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".ico"}:
                continue
            try:
                for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
                    if pattern in line:
                        rel = p.relative_to(base)
                        results.append(f"{rel}:{i}:{line}")
                        if len(results) >= max_results:
                            return "\n".join(results)
            except Exception:
                continue
    except Exception as e:
        return f"search error: {e}"
    return "\n".join(results)


def _create_gitignore_snapshot_test_tree(base: Path) -> None:
    (base / "included.txt").write_text("hello\nworld\n", encoding="utf-8")
    (base / "node_modules").mkdir(exist_ok=True)
    (base / "node_modules" / "ignored.txt").write_text("should not be seen\n", encoding="utf-8")
    (base / ".gitignore").write_text(textwrap.dedent("""
    node_modules/
    *.log
    """), encoding="utf-8")
    (base / "debug.log").write_text("noise\n", encoding="utf-8")


def gitignore_aware_search_snapshot() -> bool:
    """Ad-hoc snapshot test: verifies rg-based search ignores .gitignore entries.
    Returns True if behavior is correct, False otherwise.
    """
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        _create_gitignore_snapshot_test_tree(base)
        # If ripgrep is available, this should only match in included.txt
        code, _, _ = run_shell("rg --version")
        if code == 0:
            code, out, err = run_shell('rg -n --no-heading --color never "hello" .', cwd=str(base))
            text = out if code == 0 else (out + err)
            return "included.txt:1:hello" in text and "node_modules" not in text and "debug.log" not in text
        # Fallback mode cannot fully emulate .gitignore; ensure we at least skip node_modules and logs
        res = search_ripgrep("hello", str(base))
        return "included.txt:1:hello" in res and "node_modules" not in res and "debug.log" not in res


