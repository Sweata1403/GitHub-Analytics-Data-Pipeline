"""
Repository analytics API router.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from database import db
from schemas import RepositoryOverview, RepositoryList

router = APIRouter(prefix="/repositories", tags=["Repositories"])


@router.get("", response_model=RepositoryList)
async def list_repositories(
    sort_by: str = Query("stars_count", enum=["stars_count", "forks_count", "total_commits", "name"]),
    order: str = Query("desc", enum=["asc", "desc"]),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    language: str | None = Query(None, description="Filter by primary language"),
):
    """List all tracked repositories with aggregated stats."""
    where_clause = ""
    params = []

    if language:
        where_clause = "WHERE language = $1"
        params.append(language)

    order_dir = "DESC" if order == "desc" else "ASC"

    # Use the pre-built view
    query = f"""
        SELECT * FROM v_repository_overview
        {where_clause}
        ORDER BY {sort_by} {order_dir}
        LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
    """
    params.extend([limit, offset])

    rows = await db.fetch(query, *params)

    count_query = f"SELECT COUNT(*) FROM v_repository_overview {where_clause}"
    total = await db.fetchval(count_query, *(params[:1] if language else []))

    return RepositoryList(
        repositories=[RepositoryOverview(**row) for row in rows],
        total_count=total,
    )


@router.get("/{repository_id}", response_model=RepositoryOverview)
async def get_repository(repository_id: int):
    """Get detailed overview for a single repository."""
    row = await db.fetchrow(
        "SELECT * FROM v_repository_overview WHERE repository_id = $1",
        repository_id,
    )
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Repository not found")
    return RepositoryOverview(**row)


@router.get("/languages/unique")
async def get_unique_languages():
    """Get list of all unique languages across repositories."""
    rows = await db.fetch(
        "SELECT DISTINCT language FROM dim_repository WHERE language IS NOT NULL ORDER BY language"
    )
    return [row["language"] for row in rows]
