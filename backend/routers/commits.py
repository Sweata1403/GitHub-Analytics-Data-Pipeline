"""
Commit analytics API router.
"""

from fastapi import APIRouter, Query

from database import db
from schemas import CommitTimeline, CommitTimelinePoint, TopContributor

router = APIRouter(prefix="/commits", tags=["Commits"])


@router.get("/timeline", response_model=CommitTimeline)
async def get_commit_timeline(
    repository_id: int | None = Query(None, description="Filter by repository"),
    period: str = Query("daily", enum=["daily", "weekly", "monthly"]),
    limit: int = Query(90, ge=7, le=365, description="Number of periods to return"),
):
    """Get commit activity over time."""
    if period == "daily":
        date_trunc = "day"
    elif period == "weekly":
        date_trunc = "week"
    else:
        date_trunc = "month"

    where_clause = ""
    params = []

    if repository_id is not None:
        where_clause = "WHERE fc.repository_id = $1"
        params.append(repository_id)

    query = f"""
        SELECT
            DATE_TRUNC('{date_trunc}', d.full_date)::DATE AS date,
            COUNT(fc.commit_id) AS commit_count,
            COUNT(DISTINCT fc.author_id) AS unique_authors,
            COALESCE(SUM(fc.additions), 0)::INTEGER AS additions,
            COALESCE(SUM(fc.deletions), 0)::INTEGER AS deletions
        FROM fact_commits fc
        JOIN dim_date d ON fc.date_id = d.date_id
        {where_clause}
        GROUP BY DATE_TRUNC('{date_trunc}', d.full_date)
        ORDER BY date DESC
        LIMIT ${len(params) + 1}
    """
    params.append(limit)

    rows = await db.fetch(query, *params)

    # Total commits
    total_query = f"SELECT COUNT(*) FROM fact_commits fc {where_clause}"
    total = await db.fetchval(total_query, *(params[:1] if repository_id else []))

    return CommitTimeline(
        data=[CommitTimelinePoint(**row) for row in reversed(rows)],
        total_commits=total or 0,
        period=period,
    )


@router.get("/top-contributors", response_model=list[TopContributor])
async def get_top_contributors(
    repository_id: int | None = Query(None, description="Filter by repository"),
    limit: int = Query(20, ge=1, le=100),
):
    """Get top contributors ranked by commit count."""
    if repository_id is not None:
        query = """
            SELECT
                u.login,
                u.avatar_url,
                COUNT(DISTINCT fc.commit_id) AS total_commits,
                COUNT(DISTINCT fc.repository_id) AS repos_contributed_to,
                COALESCE(SUM(fc.additions), 0)::BIGINT AS total_additions,
                COALESCE(SUM(fc.deletions), 0)::BIGINT AS total_deletions,
                MIN(fc.authored_at) AS first_commit,
                MAX(fc.authored_at) AS last_commit
            FROM dim_user u
            JOIN fact_commits fc ON u.user_id = fc.author_id
            WHERE fc.repository_id = $1
            GROUP BY u.user_id, u.login, u.avatar_url
            ORDER BY total_commits DESC
            LIMIT $2
        """
        rows = await db.fetch(query, repository_id, limit)
    else:
        query = """
            SELECT * FROM v_top_contributors
            LIMIT $1
        """
        rows = await db.fetch(query, limit)

    return [TopContributor(**row) for row in rows]


@router.get("/heatmap")
async def get_commit_heatmap(
    repository_id: int | None = Query(None),
    year: int | None = Query(None),
):
    """
    Get commit counts by day-of-week and hour for a heatmap visualization.
    Returns 7×24 grid of commit counts.
    """
    where_clauses = []
    params = []

    if repository_id is not None:
        params.append(repository_id)
        where_clauses.append(f"fc.repository_id = ${len(params)}")

    if year is not None:
        params.append(year)
        where_clauses.append(f"d.year = ${len(params)}")

    where = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    query = f"""
        SELECT
            d.day_of_week,
            d.day_name,
            EXTRACT(HOUR FROM fc.authored_at)::INTEGER AS hour,
            COUNT(*) AS commit_count
        FROM fact_commits fc
        JOIN dim_date d ON fc.date_id = d.date_id
        {where}
        GROUP BY d.day_of_week, d.day_name, EXTRACT(HOUR FROM fc.authored_at)
        ORDER BY d.day_of_week, hour
    """
    rows = await db.fetch(query, *params)

    return [dict(row) for row in rows]
