from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List
from urllib.parse import urlparse

from github import Github


@dataclass
class GitHubIssue:
    number: int
    title: str
    body: str
    labels: List[str]


class GitHubClient:
    def __init__(self, token: str, repo_url: str) -> None:
        self._gh = Github(token)
        parsed = urlparse(repo_url)
        path = parsed.path.lstrip("/").rstrip("/")
        if path.endswith(".git"):
            path = path[:-4]
        self._repo_full_name = path
        self._repo = self._gh.get_repo(self._repo_full_name)

    @property
    def repo_full_name(self) -> str:
        return self._repo_full_name

    def find_issue_with_label(self, label: str, specific_issue: Optional[int] = None) -> Optional[GitHubIssue]:
        if specific_issue is not None:
            issue = self._repo.get_issue(number=specific_issue)
            return GitHubIssue(
                number=issue.number,
                title=issue.title or "",
                body=issue.body or "",
                labels=[l.name for l in issue.labels],
            )

        issues = self._repo.get_issues(state="open", labels=[label])
        for issue in issues:
            return GitHubIssue(
                number=issue.number,
                title=issue.title or "",
                body=issue.body or "",
                labels=[l.name for l in issue.labels],
            )
        return None

    def create_pull_request(self, head: str, base: str, title: str, body: str) -> str:
        pr = self._repo.create_pull(title=title, body=body, head=head, base=base)
        return pr.html_url


