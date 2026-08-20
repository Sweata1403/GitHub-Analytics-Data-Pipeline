"""
Pull Request analytics API router.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from database import db
from schemas import PRStats, PRTimelinePoint

router = APIRouter(prefix="/pull-requests", tags=["Pull Requests"])


@router.get("/stats", response_model=PRStats)
async def get_pr_stats(
    repository_id: int | None = Query(None, description="Filter by repository"),
):
    """Get aggregated PR metrics."""
    where_clause = ""
    params = []

    if repository_id is not None:
        where_clause = "WHERE repository_id = $1"
        params.append(repository_id)

    query = f"""
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
        {where_clause}
    """
    row = await db.fetchrow(query, *params)

    total = row["total_prs"] or 0
    merged = row["merged_prs"] or 0
    merge_rate = round(merged / total * 100, 1) if total > 0 else None

    return PRStats(
        **row,
        merge_rate_pct=merge_rate,
    )


@router.get("/timeline", response_model=list[PRTimelinePoint])
async def get_pr_timeline(
    repository_id: int | None = Query(None),
    period: str = Query("weekly", enum=["daily", "weekly", "monthly"]),
    limit: int = Query(52, ge=4, le=200),
):
    """Get PR activity timeline (opened/merged/closed over time)."""
    if period == "daily":
        date_trunc = "day"
    elif period == "weekly":
        date_trunc = "week"
    else:
        date_trunc = "month"

    where_clause = ""
    params = []

    if repository_id is not None:
        where_clause = "WHERE fp.repository_id = $1"
        params.append(repository_id)

    query = f"""
        SELECT
            DATE_TRUNC('{date_trunc}', d.full_date)::DATE AS date,
            COUNT(*) FILTER (WHERE fp.created_date_id = d.date_id) AS opened,
            COUNT(*) FILTER (WHERE fp.merged_date_id = d.date_id) AS merged,
            COUNT(*) FILTER (WHERE fp.closed_date_id = d.date_id AND fp.is_merged = FALSE) AS closed
        FROM fact_pull_requests fp
        JOIN dim_date d ON d.date_id IN (fp.created_date_id, fp.merged_date_id, fp.closed_date_id)
        {where_clause}
        GROUP BY DATE_TRUNC('{date_trunc}', d.full_date)
        ORDER BY date DESC
        LIMIT ${len(params) + 1}
    """
    params.append(limit)

    rows = await db.fetch(query, *params)
    return [PRTimelinePoint(**row) for row in reversed(rows)]


@router.get("/merge-time-trend")
async def get_merge_time_trend(
    repository_id: int | None = Query(None),
    period: str = Query("monthly", enum=["weekly", "monthly"]),
    limit: int = Query(12, ge=4, le=52),
):
    """Get average time-to-merge trend over time."""
    date_trunc = "week" if period == "weekly" else "month"

    where_clause = "WHERE fp.is_merged = TRUE"
    params = []

    if repository_id is not None:
        where_clause += " AND fp.repository_id = $1"
        params.append(repository_id)

    query = f"""
        SELECT
            DATE_TRUNC('{date_trunc}', fp.merged_at)::DATE AS date,
            ROUND(AVG(fp.time_to_merge_hours)::NUMERIC, 1) AS avg_hours,
            ROUND(
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY fp.time_to_merge_hours)::NUMERIC,
                1
            ) AS median_hours,
            COUNT(*) AS merged_count
        FROM fact_pull_requests fp
        {where_clause}
        GROUP BY DATE_TRUNC('{date_trunc}', fp.merged_at)
        ORDER BY date DESC
        LIMIT ${len(params) + 1}
    """
    params.append(limit)

    rows = await db.fetch(query, *params)
    return [dict(row) for row in reversed(rows)]
