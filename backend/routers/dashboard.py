"""
Dashboard summary API router.

Provides a single endpoint that aggregates all key metrics
for the main dashboard view, reducing the number of API calls
the frontend needs to make.
"""

from fastapi import APIRouter

from database import db
from schemas import (
    DashboardSummary,
    CommitTimelinePoint,
    TopContributor,
    LanguageUsage,
    PRStats,
    IssueStats,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary():
    """
    Get a complete dashboard summary in a single API call.
    Aggregates: repo count, commit count, PR stats, issue stats,
    top contributors, language distribution, and recent activity.
    """

    # --- Core Counts ---
    counts = await db.fetchrow("""
        SELECT
            (SELECT COUNT(*) FROM dim_repository) AS total_repositories,
            (SELECT COUNT(*) FROM fact_commits) AS total_commits,
            (SELECT COUNT(*) FROM fact_pull_requests) AS total_pull_requests,
            (SELECT COUNT(*) FROM fact_issues) AS total_issues,
            (SELECT COUNT(DISTINCT login) FROM dim_user) AS total_contributors,
            (SELECT COALESCE(SUM(stars_count), 0) FROM dim_repository) AS total_stars,
            (SELECT COALESCE(SUM(forks_count), 0) FROM dim_repository) AS total_forks
    """)

    # --- Top Language ---
    top_lang = await db.fetchval("""
        SELECT language FROM repo_languages
        GROUP BY language
        ORDER BY SUM(bytes) DESC
        LIMIT 1
    """)

    # --- PR Stats ---
    pr_row = await db.fetchrow("""
        SELECT
            COUNT(*) AS total_prs,
            COUNT(*) FILTER (WHERE state = 'open') AS open_prs,
            COUNT(*) FILTER (WHERE is_merged = TRUE) AS merged_prs,
            COUNT(*) FILTER (WHERE state = 'closed' AND is_merged = FALSE) AS closed_unmerged,
            ROUND(AVG(time_to_merge_hours)::NUMERIC, 1) AS avg_merge_time_hours,
            ROUND(
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY time_to_merge_hours)::NUMERIC,
                1
            ) AS median_merge_time_hours
        FROM fact_pull_requests
    """)

    pr_total = pr_row["total_prs"] or 0
    pr_merged = pr_row["merged_prs"] or 0

    pr_stats = PRStats(
        **pr_row,
        merge_rate_pct=round(pr_merged / pr_total * 100, 1) if pr_total > 0 else None,
    )

    # --- Issue Stats ---
    issue_row = await db.fetchrow("""
        SELECT
            COUNT(*) AS total_issues,
            COUNT(*) FILTER (WHERE state = 'open') AS open_issues,
            COUNT(*) FILTER (WHERE state = 'closed') AS closed_issues,
            ROUND(AVG(time_to_close_hours)::NUMERIC, 1) AS avg_close_time_hours,
            ROUND(
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY time_to_close_hours)::NUMERIC,
                1
            ) AS median_close_time_hours
        FROM fact_issues
    """)

    issue_stats = IssueStats(**issue_row)

    # --- Recent Commits (last 30 days) ---
    recent_commits = await db.fetchval("""
        SELECT COUNT(*) FROM fact_commits
        WHERE authored_at >= NOW() - INTERVAL '30 days'
    """)

    # --- Commit Timeline (last 30 days, daily) ---
    timeline_rows = await db.fetch("""
        SELECT
            d.full_date AS date,
            COUNT(fc.commit_id) AS commit_count,
            COUNT(DISTINCT fc.author_id) AS unique_authors,
            COALESCE(SUM(fc.additions), 0)::INTEGER AS additions,
            COALESCE(SUM(fc.deletions), 0)::INTEGER AS deletions
        FROM dim_date d
        LEFT JOIN fact_commits fc ON d.date_id = fc.date_id
        WHERE d.full_date >= CURRENT_DATE - INTERVAL '30 days'
          AND d.full_date <= CURRENT_DATE
        GROUP BY d.full_date
        ORDER BY d.full_date
    """)

    # --- Top Contributors (top 10) ---
    contrib_rows = await db.fetch("""
        SELECT * FROM v_top_contributors LIMIT 10
    """)

    # --- Language Distribution ---
    lang_rows = await db.fetch("""
        SELECT
            language,
            SUM(bytes)::BIGINT AS total_bytes,
            COUNT(DISTINCT repository_id) AS repo_count,
            ROUND(
                SUM(bytes)::NUMERIC / NULLIF(SUM(SUM(bytes)) OVER (), 0) * 100,
                1
            ) AS percentage
        FROM repo_languages
        GROUP BY language
        ORDER BY total_bytes DESC
        LIMIT 15
    """)

    return DashboardSummary(
        total_repositories=counts["total_repositories"],
        total_commits=counts["total_commits"],
        total_pull_requests=counts["total_pull_requests"],
        total_issues=counts["total_issues"],
        total_contributors=counts["total_contributors"],
        total_stars=counts["total_stars"],
        total_forks=counts["total_forks"],
        top_language=top_lang,
        avg_merge_time_hours=float(pr_row["avg_merge_time_hours"]) if pr_row["avg_merge_time_hours"] else None,
        open_issues=issue_row["open_issues"],
        recent_commits_30d=recent_commits or 0,
        commit_timeline=[CommitTimelinePoint(**row) for row in timeline_rows],
        top_contributors=[TopContributor(**row) for row in contrib_rows],
        language_distribution=[LanguageUsage(**row) for row in lang_rows],
        pr_stats=pr_stats,
        issue_stats=issue_stats,
    )
