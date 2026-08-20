# Data Dictionary (Gold Layer)

Source of truth is [database/schema.sql](../database/schema.sql) — this is a
human-readable summary of it.

## Dimensions

### `dim_date`
Pre-populated calendar dimension, 2020–2030 (see `database/seed_dim_date.sql`).

| Column | Type | Notes |
|---|---|---|
| date_id | INTEGER PK | `YYYYMMDD` |
| full_date | DATE | unique |
| year, quarter, month, week, day_of_month, day_of_week | SMALLINT | day_of_week: 0=Monday |
| month_name, day_name | VARCHAR | |
| is_weekend | BOOLEAN | |

### `dim_repository`
One row per GitHub repository (SCD Type 1 — overwritten on update).

| Column | Type | Notes |
|---|---|---|
| repository_id | SERIAL PK | internal surrogate key |
| github_repo_id | BIGINT | unique, GitHub's own numeric ID |
| full_name, owner, name | VARCHAR | e.g. `owner/name` |
| language, default_branch, license_name | VARCHAR | |
| is_private, is_fork | BOOLEAN | |
| stars_count, forks_count, watchers_count, open_issues_count, size_kb | INTEGER | default 0 |
| created_at, updated_at | TIMESTAMPTZ | from GitHub |
| etl_loaded_at | TIMESTAMPTZ | when this row was last written by the gold ETL |

### `dim_user`
One row per GitHub user seen across ingested repos.

| Column | Type | Notes |
|---|---|---|
| user_id | SERIAL PK | |
| github_user_id | BIGINT | unique |
| login | VARCHAR | unique index |
| user_type | VARCHAR | `User`, `Bot`, or `Organization` |
| avatar_url, html_url | VARCHAR | |

## Facts

### `fact_commits`
| Column | Type | Notes |
|---|---|---|
| commit_id | SERIAL PK | |
| sha | VARCHAR(40) | unique with repository_id |
| repository_id, author_id, committer_id, date_id | FK | |
| additions, deletions, files_changed | INTEGER | |
| net_lines | INTEGER, generated | `additions - deletions` |
| authored_at | TIMESTAMPTZ | |

### `fact_pull_requests`
| Column | Type | Notes |
|---|---|---|
| pr_id | SERIAL PK | |
| github_pr_id, number | | unique with repository_id |
| state | VARCHAR | `open` / `closed` |
| is_merged, is_draft | BOOLEAN | |
| time_to_merge_hours | DOUBLE PRECISION | null until merged |
| created_at, merged_at, closed_at | TIMESTAMPTZ | |

### `fact_issues`
| Column | Type | Notes |
|---|---|---|
| issue_id | SERIAL PK | |
| github_issue_id, number | | unique with repository_id |
| state | VARCHAR | `open` / `closed` |
| labels, assignees | TEXT[] | Postgres arrays |
| time_to_close_hours | DOUBLE PRECISION | null until closed |

## Supplementary

- **`repo_languages`** — bytes + percentage per language per repository.
- **`pipeline_runs`** — audit log of each ingestion/ETL run (status, counts, errors).

## Views (used by the FastAPI backend)

| View | Purpose |
|---|---|
| `v_repository_overview` | per-repo aggregated commit/PR/issue counts |
| `v_daily_commit_activity` | commits per repo per day, for timeline charts |
| `v_pr_metrics` | merge rate and merge-time stats per repo |
| `v_top_contributors` | commit leaderboard across all ingested repos |
