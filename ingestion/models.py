"""
Data models representing GitHub entities.

These models define the structure of data as extracted from the
GitHub API before uploading to the Bronze layer (S3).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any


@dataclass
class Repository:
    """Represents a GitHub repository."""
    id: int
    full_name: str
    owner: str
    name: str
    description: str | None
    language: str | None
    default_branch: str
    is_private: bool
    is_fork: bool
    stars_count: int
    forks_count: int
    watchers_count: int
    open_issues_count: int
    size_kb: int
    created_at: str
    updated_at: str
    pushed_at: str | None
    topics: list[str] = field(default_factory=list)
    license_name: str | None = None
    html_url: str = ""

    @classmethod
    def from_api(cls, data: dict) -> "Repository":
        """Create a Repository from GitHub API response."""
        return cls(
            id=data["id"],
            full_name=data["full_name"],
            owner=data["owner"]["login"],
            name=data["name"],
            description=data.get("description"),
            language=data.get("language"),
            default_branch=data.get("default_branch", "main"),
            is_private=data.get("private", False),
            is_fork=data.get("fork", False),
            stars_count=data.get("stargazers_count", 0),
            forks_count=data.get("forks_count", 0),
            watchers_count=data.get("watchers_count", 0),
            open_issues_count=data.get("open_issues_count", 0),
            size_kb=data.get("size", 0),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            pushed_at=data.get("pushed_at"),
            topics=data.get("topics", []),
            license_name=(data.get("license") or {}).get("spdx_id"),
            html_url=data.get("html_url", ""),
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Commit:
    """Represents a GitHub commit."""
    sha: str
    repository_full_name: str
    author_login: str | None
    author_name: str
    author_email: str
    author_date: str
    committer_login: str | None
    committer_name: str
    committer_date: str
    message: str
    additions: int = 0
    deletions: int = 0
    files_changed: int = 0
    html_url: str = ""

    @classmethod
    def from_api(cls, data: dict, repo_full_name: str) -> "Commit":
        """Create a Commit from GitHub API response."""
        commit_data = data.get("commit", {})
        author = commit_data.get("author", {})
        committer = commit_data.get("committer", {})
        stats = data.get("stats", {})

        return cls(
            sha=data["sha"],
            repository_full_name=repo_full_name,
            author_login=(data.get("author") or {}).get("login"),
            author_name=author.get("name", "Unknown"),
            author_email=author.get("email", ""),
            author_date=author.get("date", ""),
            committer_login=(data.get("committer") or {}).get("login"),
            committer_name=committer.get("name", "Unknown"),
            committer_date=committer.get("date", ""),
            message=commit_data.get("message", ""),
            additions=stats.get("additions", 0),
            deletions=stats.get("deletions", 0),
            files_changed=stats.get("total", 0),
            html_url=data.get("html_url", ""),
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PullRequest:
    """Represents a GitHub pull request."""
    id: int
    number: int
    repository_full_name: str
    title: str
    state: str
    author_login: str | None
    created_at: str
    updated_at: str
    closed_at: str | None
    merged_at: str | None
    is_merged: bool
    comments_count: int
    review_comments_count: int
    commits_count: int
    additions: int
    deletions: int
    changed_files: int
    labels: list[str] = field(default_factory=list)
    html_url: str = ""
    draft: bool = False

    @classmethod
    def from_api(cls, data: dict, repo_full_name: str) -> "PullRequest":
        """Create a PullRequest from GitHub API response."""
        return cls(
            id=data["id"],
            number=data["number"],
            repository_full_name=repo_full_name,
            title=data.get("title", ""),
            state=data.get("state", ""),
            author_login=(data.get("user") or {}).get("login"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            closed_at=data.get("closed_at"),
            merged_at=data.get("merged_at"),
            is_merged=data.get("merged_at") is not None,
            comments_count=data.get("comments", 0),
            review_comments_count=data.get("review_comments", 0),
            commits_count=data.get("commits", 0),
            additions=data.get("additions", 0),
            deletions=data.get("deletions", 0),
            changed_files=data.get("changed_files", 0),
            labels=[label.get("name", "") for label in data.get("labels", [])],
            html_url=data.get("html_url", ""),
            draft=data.get("draft", False),
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Issue:
    """Represents a GitHub issue (excludes pull requests)."""
    id: int
    number: int
    repository_full_name: str
    title: str
    state: str
    author_login: str | None
    created_at: str
    updated_at: str
    closed_at: str | None
    comments_count: int
    labels: list[str] = field(default_factory=list)
    assignees: list[str] = field(default_factory=list)
    milestone: str | None = None
    html_url: str = ""

    @classmethod
    def from_api(cls, data: dict, repo_full_name: str) -> "Issue":
        """Create an Issue from GitHub API response."""
        return cls(
            id=data["id"],
            number=data["number"],
            repository_full_name=repo_full_name,
            title=data.get("title", ""),
            state=data.get("state", ""),
            author_login=(data.get("user") or {}).get("login"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            closed_at=data.get("closed_at"),
            comments_count=data.get("comments", 0),
            labels=[label.get("name", "") for label in data.get("labels", [])],
            assignees=[a.get("login", "") for a in data.get("assignees", [])],
            milestone=(data.get("milestone") or {}).get("title"),
            html_url=data.get("html_url", ""),
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Contributor:
    """Represents a GitHub contributor."""
    id: int
    login: str
    repository_full_name: str
    contributions: int
    avatar_url: str
    type: str  # 'User' or 'Bot'
    html_url: str = ""

    @classmethod
    def from_api(cls, data: dict, repo_full_name: str) -> "Contributor":
        """Create a Contributor from GitHub API response."""
        return cls(
            id=data["id"],
            login=data["login"],
            repository_full_name=repo_full_name,
            contributions=data.get("contributions", 0),
            avatar_url=data.get("avatar_url", ""),
            type=data.get("type", "User"),
            html_url=data.get("html_url", ""),
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LanguageBreakdown:
    """Represents language usage in a repository."""
    repository_full_name: str
    languages: dict[str, int]  # {language: bytes}
    total_bytes: int = 0

    @classmethod
    def from_api(cls, data: dict, repo_full_name: str) -> "LanguageBreakdown":
        """Create a LanguageBreakdown from GitHub API response."""
        total = sum(data.values()) if data else 0
        return cls(
            repository_full_name=repo_full_name,
            languages=data,
            total_bytes=total,
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class IngestionMetadata:
    """Metadata about an ingestion run."""
    run_id: str
    started_at: str
    completed_at: str | None = None
    status: str = "running"  # running, completed, failed
    repos_processed: int = 0
    total_entities: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
