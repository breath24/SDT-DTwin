from __future__ import annotations

from urllib.parse import quote, urlparse
import re


def to_https_url(repo_url: str) -> str:
    """Normalize a repository reference into an https URL.
    Accepts forms:
    - git@github.com:owner/repo(.git)
    - https://github.com/owner/repo(.git)
    - owner/repo(.git)  → assumes GitHub
    Returns https URL with .git suffix preserved/added.
    """
    if repo_url.startswith("git@github.com:"):
        path = repo_url.split(":", 1)[1]
        if not path.endswith(".git"):
            path += ".git"
        return f"https://github.com/{path}"

    parsed = urlparse(repo_url)
    if parsed.scheme in {"http", "https"}:
        return repo_url

    # owner/repo form without scheme
    if re.fullmatch(r"[\w.-]+/[\w.-]+(?:\.git)?", repo_url):
        path = repo_url
        if not path.endswith(".git"):
            path += ".git"
        return f"https://github.com/{path}"

    return repo_url


def with_token(repo_url: str, token: str | None) -> str:
    if not token:
        return repo_url
    url = to_https_url(repo_url)
    if url.startswith("https://") and "@" not in url:
        safe_token = quote(token, safe="")
        return url.replace("https://", f"https://{safe_token}@")
    return url


