"""
Pydantic response schemas for the FastAPI analytics API.
"""

from __future__ import annotations

from datetime import datetime, date
from pydantic import BaseModel, Field


# =====================================================================
# Repository Schemas
# =====================================================================

class RepositoryOverview(BaseModel):
    repository_id: int
    full_name: str
    owner: str
    name: str
    description: str | None = None
    language: str | None = None
    stars_count: int = 0
    forks_count: int = 0
    is_fork: bool = False
    created_at: datetime | None = None
    html_url: str | None = None
    total_commits: int = 0
    total_prs: int = 0
    total_issues: int = 0
    total_additions: int = 0
    total_deletions: int = 0


class RepositoryList(BaseModel):
    repositories: list[RepositoryOverview]
    total_count: int


# =====================================================================
# Commit Schemas
# =====================================================================

class CommitTimelinePoint(BaseModel):
    date: date
    commit_count: int
    unique_authors: int
    additions: int = 0
    deletions: int = 0


class CommitTimeline(BaseModel):
    data: list[CommitTimelinePoint]
    total_commits: int
    period: str = "daily"


class TopContributor(BaseModel):
    login: str
    avatar_url: str | None = None
    total_commits: int
    repos_contributed_to: int
    total_additions: int = 0
    total_deletions: int = 0
    first_commit: datetime | None = None
    last_commit: datetime | None = None


# =====================================================================
# Pull Request Schemas
# =====================================================================

class PRStats(BaseModel):
    total_prs: int = 0
    open_prs: int = 0
    merged_prs: int = 0
    closed_unmerged: int = 0
    avg_merge_time_hours: float | None = None
    median_merge_time_hours: float | None = None
    merge_rate_pct: float | None = None


class PRTimelinePoint(BaseModel):
    date: date
    opened: int = 0
    merged: int = 0
    closed: int = 0


# =====================================================================
# Issue Schemas
# =====================================================================

class IssueStats(BaseModel):
    total_issues: int = 0
    open_issues: int = 0
    closed_issues: int = 0
    avg_close_time_hours: float | None = None
    median_close_time_hours: float | None = None


class IssueTimelinePoint(BaseModel):
    date: date
    opened: int = 0
    closed: int = 0


class LabelDistribution(BaseModel):
    label: str
    count: int


# =====================================================================
# Language Schemas
# =====================================================================

class LanguageUsage(BaseModel):
    language: str
    total_bytes: int
    repo_count: int
    percentage: float = 0.0


# =====================================================================
# Dashboard Summary Schema
# =====================================================================

class DashboardSummary(BaseModel):
    total_repositories: int = 0
    total_commits: int = 0
    total_pull_requests: int = 0
    total_issues: int = 0
    total_contributors: int = 0
    total_stars: int = 0
    total_forks: int = 0
    top_language: str | None = None
    avg_merge_time_hours: float | None = None
    open_issues: int = 0
    recent_commits_30d: int = 0
    commit_timeline: list[CommitTimelinePoint] = []
    top_contributors: list[TopContributor] = []
    language_distribution: list[LanguageUsage] = []
    pr_stats: PRStats = Field(default_factory=PRStats)
    issue_stats: IssueStats = Field(default_factory=IssueStats)


# =====================================================================
# Health Check
# =====================================================================

class HealthCheck(BaseModel):
    status: str = "healthy"
    database: str = "connected"
    version: str = "1.0.0"
