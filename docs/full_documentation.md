# GitHub Analytics Data Pipeline — Full Documentation

---

## Table of Contents

1. [What Is This Project?](#1-what-is-this-project)
2. [Why Was It Built?](#2-why-was-it-built)
3. [The Problem It Solves](#3-the-problem-it-solves)
4. [High-Level Flow](#4-high-level-flow)
5. [Medallion Architecture (Bronze / Silver / Gold)](#5-medallion-architecture)
6. [Ingestion Layer](#6-ingestion-layer)
7. [Bronze → Silver ETL](#7-bronze--silver-etl)
8. [Silver → Gold ETL](#8-silver--gold-etl)
9. [Database Design (Star Schema)](#9-database-design-star-schema)
10. [FastAPI Backend](#10-fastapi-backend)
11. [Next.js Dashboard](#11-nextjs-dashboard)
12. [Deployment Options](#12-deployment-options)
13. [Technology Choices — Explained](#13-technology-choices--explained)
14. [Limitations & Future Improvements](#14-limitations--future-improvements)

---

## 1. What Is This Project?

The **GitHub Analytics Data Pipeline** is a full-stack data engineering project that:

- Pulls raw activity data from the GitHub REST API (repositories, commits, pull requests,
  issues, contributors, and programming language statistics)
- Processes that data through a three-layer **Medallion architecture** (Bronze → Silver → Gold)
  using Apache PySpark
- Persists the cleaned, structured data into a **PostgreSQL star schema** database
- Exposes the data through an **async FastAPI** REST backend
- Renders it in an interactive **Next.js + Recharts** dashboard

The end result is a live analytics platform that answers questions like "which repositories
have the most commits?", "who are the most active contributors?", and "how has activity
changed month over month?" — all pulled from real GitHub data.

---

## 2. Why Was It Built?

This project was built to demonstrate core data engineering competencies in a single,
end-to-end portfolio project:

**Data ingestion** — calling a real third-party API, handling pagination, rate limits, and
authentication with personal access tokens.

**ETL at scale** — using PySpark (the industry standard for large-scale data processing)
to transform raw JSON into clean, deduplicated, typed Parquet files, then loading those
into a relational database with proper surrogate key resolution.

**Data modelling** — designing a Kimball-style star schema: separating facts (events that
happened — commits, PRs, issues) from dimensions (who, what, when), which makes analytical
queries fast and readable.

**Backend engineering** — building an async REST API with FastAPI and asyncpg, using
connection pooling rather than per-request connections for performance, with auto-generated
Swagger documentation.

**Frontend integration** — connecting the API to a React-based dashboard that visualises
the data with Recharts, demonstrating how data flows all the way from source API to the
end user's screen.

**Cloud awareness** — the architecture is designed to swap local components (local
PostgreSQL, localhost FastAPI) for cloud equivalents (AWS RDS or Neon, Render, Vercel)
with only environment variable changes.

---

## 3. The Problem It Solves

GitHub provides a powerful API, but its data is spread across many endpoints and is not
designed for analytics. To answer a question like "what percentage of commits across all
our repos came from external contributors last month?", you would need to:

- Fetch every repo
- Fetch every commit for every repo with date filters
- Cross-reference against the contributors list
- Deduplicate (GitHub sometimes returns the same commit from multiple endpoints)
- Aggregate across repos

Doing this on the fly for every dashboard page load would be slow, rate-limited, and
fragile. This pipeline solves that by **moving the data once**, cleaning it, storing it
in a format optimised for queries, and serving pre-structured responses through an API.

The result: the dashboard loads in milliseconds because all the heavy lifting (API calls,
deduplication, joins) was done ahead of time by the pipeline.

---

## 4. High-Level Flow

```
Developer runs ingestion → Raw JSON in Bronze layer
         ↓
Developer runs bronze_to_silver.py → Clean Parquet in Silver layer
         ↓
Developer runs silver_to_gold.py → Star schema populated in PostgreSQL
         ↓
FastAPI backend reads PostgreSQL → Exposes REST endpoints
         ↓
Next.js dashboard calls API → Renders charts in browser
```

Each step is independent. You can re-run any layer in isolation — for example, re-ingest
only new data, re-process only Silver without re-ingesting, or redeploy only the backend
without touching the database.

---

## 5. Medallion Architecture

The Medallion architecture (popularised by Databricks) organises data into three zones of
increasing quality and structure.

### Bronze — Raw Data Landing Zone

**Location:** `data/bronze/{entity}/year=YYYY/month=MM/day=DD/`

Bronze is the raw, unmodified dump from the GitHub API. Every API response is written as
a JSON file into a **Hive-style partitioned** folder structure. No transformations happen
here — what comes from GitHub is what goes in.

**Why Hive partitioning?**  
The folder structure (`year=2026/month=08/day=20/`) is not just for organisation. PySpark
reads partition folders natively. When you filter by date, Spark only opens the relevant
subfolders instead of scanning every file — this is called **partition pruning** and
dramatically reduces I/O for large datasets.

**Why keep Bronze immutable?**  
Bronze is the audit trail. If a bug in the Silver ETL produces wrong data, you can always
re-run Silver from Bronze without going back to GitHub. This matters because GitHub API
responses can change over time (repo deleted, user renamed), and old API calls cannot be
replayed. Bronze preserves the state of GitHub at the time of ingestion.

### Silver — Cleaned & Deduplicated

**Location:** `data/silver/`  
**Format:** Parquet

Silver is Bronze after cleaning. The PySpark job (`bronze_to_silver.py`) applies:

- **Type casting**: string timestamps become `TimestampType`, counts become `LongType`,
  booleans are normalised
- **Deduplication**: `dropDuplicates()` on natural keys (commit SHA, PR number, issue
  number) removes rows that appeared in multiple API responses
- **Schema enforcement**: a fixed schema is applied so downstream jobs never guess types

**Why Parquet?**  
Parquet is a columnar format. In a row-based format (CSV, JSON), reading one column means
scanning every byte of every row. In Parquet, columns are stored contiguously — reading
just `commit_sha` and `committed_at` reads only those two columns from disk. For analytics
(which typically touches a few columns across millions of rows), this is an order of
magnitude faster. Snappy compression (Parquet's default) also shrinks file sizes by 3–5×.

**Result from this project:** 2,662 raw commit records → 874 after deduplication.

### Gold — Analytics-Ready Star Schema

**Location:** PostgreSQL database  
**Tables:** dimension tables + fact tables + views

Gold is the data in its most useful form for answering business questions. PySpark reads
Silver Parquet, resolves surrogate keys by joining against dimension tables via JDBC, and
writes the results into PostgreSQL. PostgreSQL views provide pre-joined, pre-aggregated
perspectives for the most common queries.

---

## 6. Ingestion Layer

**File:** `ingestion/ingest.py`  
**Config:** `ingestion/config.py`

The ingestion layer authenticates to the GitHub API using a fine-grained Personal Access
Token (PAT) and fetches six entity types per repository:

| Entity | GitHub API endpoint | What it captures |
|---|---|---|
| Repositories | `/user/repos`, `/users/{user}/repos` | Repo metadata, stars, forks, language |
| Commits | `/repos/{owner}/{repo}/commits` | SHA, author, message, timestamp |
| Pull Requests | `/repos/{owner}/{repo}/pulls?state=all` | Title, state, author, merge date |
| Issues | `/repos/{owner}/{repo}/issues?state=all` | Title, state, labels, close date |
| Contributors | `/repos/{owner}/{repo}/contributors` | Username, contribution count |
| Languages | `/repos/{owner}/{repo}/languages` | Language name → bytes of code |

**Configuration via `config.py`:**  
Credentials and settings are loaded from `.env` into typed Python dataclasses
(`GitHubConfig`, `RDSConfig`, `PipelineConfig`). This avoids scattered `os.getenv()`
calls throughout the codebase and provides a single, documented place for all config.

**Flags:**
- `--local` — writes JSON to `data/bronze/` instead of S3
- `--max-repos N` — cap repos per user (useful for quick tests)
- `--repos owner/repo` — ingest a single specific repo

---

## 7. Bronze → Silver ETL

**File:** `etl/bronze_to_silver.py`  
**Engine:** Apache PySpark

This PySpark job reads all Bronze JSON files, applies transformations, and writes Silver
Parquet. It runs locally on your machine using Spark's local mode — no cluster required.

**Key transformations per entity:**

- **Commits:** cast `committed_at` string → `TimestampType`; `dropDuplicates(["sha"])`
- **Pull Requests:** cast `created_at`, `merged_at`, `closed_at`; `dropDuplicates(["number", "repository_full_name"])`
- **Issues:** same pattern as PRs
- **Languages:** each repo's language map stored as a struct keyed by language name

**Why PySpark and not pandas?**  
Pandas is excellent for datasets that fit comfortably in memory (typically under a few
hundred MB). PySpark distributes processing across CPU cores (or cluster nodes) and can
handle datasets that are larger than available RAM using disk spill. Using PySpark here
demonstrates familiarity with the industry-standard tool for large-scale ETL, even if the
current dataset is small enough for pandas. The code would work unchanged on a 100TB dataset
running on an EMR or Databricks cluster.

---

## 8. Silver → Gold ETL

**File:** `etl/silver_to_gold.py`  
**Engine:** PySpark + JDBC (PostgreSQL JDBC driver: `postgresql-42.6.0.jar`)

This is the most complex ETL step. It reads Silver Parquet files and writes into the
PostgreSQL star schema. The challenge is **surrogate key resolution**: fact tables store
integer foreign keys (`repository_id`, `user_id`, `date_id`), not the raw string values
from GitHub. The ETL resolves them like this:

```
Silver Parquet row: { "repository_full_name": "Sweata1403/my-repo", ... }

JDBC lookup: SELECT repository_id FROM dim_repository
             WHERE github_full_name = "Sweata1403/my-repo"
             → returns: 7

Fact row written: { "repository_id": 7, "commit_sha": "abc123", ... }
```

**Known limitation — idempotency:**  
The ETL uses `mode="append"` for all writes. Running it twice without truncating the Gold
tables first produces duplicate key violations. The proper solution is `INSERT … ON CONFLICT
DO UPDATE` (upsert), but this requires moving away from PySpark's JDBC writer to custom
SQL. The current workaround is to `TRUNCATE … RESTART IDENTITY CASCADE` before each run.
This is documented in the Runbook and is a common interview discussion point.

**Languages struct → map conversion:**  
GitHub's language response (`{"Python": 45000, "JavaScript": 12000}`) is stored in Bronze
as a JSON object. When PySpark reads it from Parquet, it infers it as a STRUCT (one fixed
field per language) rather than a MAP (dynamic keys). `F.explode()` requires MAP or ARRAY,
not STRUCT. The fix dynamically converts the struct to a map using `F.create_map()` before
exploding into one row per language per repository.

---

## 9. Database Design (Star Schema)

**File:** `database/schema.sql`

The database follows the **Kimball star schema** pattern, which separates data into two
types of tables:

**Dimension tables** describe the "who", "what", and "when":
- `dim_repository` — one row per repo (name, description, stars, fork count, primary language)
- `dim_user` — one row per GitHub user (login, display name, avatar URL)
- `dim_date` — one row per calendar day from 2020 to 2030, pre-populated with derived
  columns (year, month, day, quarter, day of week, is_weekend) for fast time-based filters

**Fact tables** record events (the "what happened"):
- `fact_commits` — one row per commit (sha, author, date, additions, deletions, FK to repo + user + date)
- `fact_pull_requests` — one row per PR (state, merged flag, dates, FK to repo + author + date)
- `fact_issues` — one row per issue (state, labels, dates, FK to repo + author + date)
- `repo_languages` — one row per repo–language pair (bytes of code per language)

**Views** provide pre-joined analytical perspectives:
- `v_repository_overview` — joins dim_repository with counts from all fact tables
- `v_daily_commit_activity` — daily commit counts with date attributes for trend charts
- `v_pr_metrics` — PR merge rates, average time to merge
- `v_top_contributors` — ranked by total commits across all repos

**Why a star schema vs. a normalised (3NF) schema?**  
A 3NF schema would further normalise dimension data (e.g. a separate `languages` lookup
table, a `users` table referenced from a `repository_owners` table). This reduces storage
but requires more joins for analytical queries. A star schema trades some storage for query
simplicity — a single join from any fact to its dimension gives all the descriptive context.
This is the standard for analytical (OLAP) workloads where read performance matters more
than write efficiency.

**Why pre-populate `dim_date`?**  
Date dimension rows are never looked up by joining to a live calendar — the rows exist
before any data is loaded. `seed_dim_date.sql` inserts 4,018 rows covering 2020–2030.
This means every ETL run can resolve `date_id` instantly via a simple date match
(`WHERE full_date = '2026-08-20'`) rather than generating date attributes at query time.

---

## 10. FastAPI Backend

**Files:** `backend/main.py`, `backend/database.py`, `backend/routers/`

### Application structure

`main.py` creates the FastAPI application with:
- A **lifespan** context manager that opens the database connection pool on startup and
  closes it cleanly on shutdown
- **CORS middleware** that allows the Next.js frontend (running on a different port or domain)
  to call the API
- Four routers mounted under `/api/v1`: repositories, commits, pull_requests, dashboard
- A health endpoint at `/api/v1/health` that verifies the database connection is live

### Connection pooling with asyncpg

`database.py` manages a single **asyncpg connection pool** shared across the whole
application. The pool starts with 2 connections and scales up to 10 under load.

**Why a pool and not per-request connections?**  
Opening a PostgreSQL connection involves a TCP handshake, SSL negotiation, and authentication.
This takes 50–150ms. Under load (100 requests/second), creating a new connection for each
request would consume that time on every single request and overwhelm the database with
connection overhead. A pool keeps connections open and reuses them — requests wait
microseconds to borrow a connection from the pool rather than hundreds of milliseconds to
open a new one.

**Why URL-encode the password?**  
asyncpg accepts a connection string in the form `postgresql://user:pass@host/db`. If the
password contains special characters like `@`, `:`, or `/`, the URL parser misreads the
structure — an `@` inside the password looks like the separator between credentials and
host. `urllib.parse.quote_plus()` encodes these characters (`@` → `%40`, `:` → `%3A`),
so the parser always reads the string correctly.

### API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/health` | Database connection check |
| GET | `/api/v1/repositories` | All repos with stats |
| GET | `/api/v1/repositories/{id}` | Single repo detail |
| GET | `/api/v1/commits` | Paginated commit list |
| GET | `/api/v1/pull_requests` | PR list with filters |
| GET | `/api/v1/dashboard/overview` | Aggregated KPI summary |
| GET | `/api/v1/dashboard/commit_activity` | Daily commit trend |
| GET | `/api/v1/dashboard/top_contributors` | Ranked contributor list |
| GET | `/api/v1/dashboard/language_distribution` | Language breakdown |

Swagger UI (auto-generated by FastAPI) is available at `/api/v1/docs`.

---

## 11. Next.js Dashboard

**Directory:** `dashboard/`  
**Stack:** Next.js 16, React 19, Recharts, TypeScript

The dashboard is a Next.js application that reads `NEXT_PUBLIC_API_URL` from `.env.local`
and calls the FastAPI backend. The `NEXT_PUBLIC_` prefix is Next.js's mechanism for marking
environment variables safe to bundle into client-side JavaScript — without it, the variable
would only be available in server-side code and the browser could not call the API directly.

**Visualisations (Recharts):**
- Line or bar chart for daily commit activity (trend over time)
- Bar chart for top contributors (commits per user)
- Pie or bar chart for language distribution (bytes per language)
- Summary cards for total repos, commits, PRs, issues

**Local vs deployed:**  
The only change needed to point the dashboard at a deployed backend is updating
`NEXT_PUBLIC_API_URL` in `.env.local` (or as an environment variable in Vercel):

```
# Local
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1

# Deployed
NEXT_PUBLIC_API_URL=https://your-app.onrender.com/api/v1
```

---

## 12. Deployment Options

### Local (development)
- PostgreSQL: local installation
- FastAPI: `python -m uvicorn main:app --port 8000`
- Dashboard: `npm run dev` on port 3000

### Cloud (production-like)
- **Database:** AWS RDS PostgreSQL (free tier, 12 months) or Neon (always free, 0.5 GB)
- **Backend:** Render (free tier — spins down after 15 min inactivity; first request wakes it in ~30s)
- **Dashboard:** Vercel (free tier, instant global CDN)

The pipeline itself (ingestion + PySpark ETL) always runs locally or on a dedicated compute
instance — PySpark is not suitable for serverless environments. Only the serving layer
(FastAPI + Next.js) is deployed.

---

## 13. Technology Choices — Explained

### Why PySpark over pandas?
PySpark is the industry standard for large-scale data processing. It uses a distributed
execution model (even in local mode, across CPU cores) and handles datasets larger than
RAM. Using PySpark demonstrates familiarity with the tool used in almost every data
engineering role. The code is portable — it runs unchanged on a local laptop and on a
multi-node EMR or Databricks cluster.

### Why FastAPI over Flask or Django?
FastAPI is async-first, which means it can handle many concurrent I/O-bound requests
(database queries) without blocking. It auto-generates OpenAPI/Swagger documentation from
type annotations, reducing boilerplate. Pydantic validation ensures all request/response
data conforms to defined schemas. It is the current standard for Python data APIs.

### Why asyncpg over psycopg2?
asyncpg is a pure-async PostgreSQL driver written in Cython for performance. It does not
use DBAPI2 and cannot be used with synchronous code, but in an async FastAPI application
it is 2–3× faster than psycopg2 for high-concurrency workloads. asyncpg's connection pool
is also simpler to configure than SQLAlchemy's pool layer.

### Why PostgreSQL over a data warehouse (BigQuery, Snowflake)?
For a dataset of this size (thousands to low millions of rows), PostgreSQL with proper
indexing is more than capable. Data warehouses add operational overhead (billing, IAM,
connector setup) that is not justified at this scale. PostgreSQL also supports views and
FK constraints which enforce data integrity at the database level — something columnar
data warehouses do not always guarantee.

### Why Next.js over a pure React app (CRA / Vite)?
Next.js provides server-side rendering (SSR) and the App Router, which allows some data
fetching to happen on the server before the page is sent to the browser. This improves
initial load performance and is the current React production standard. It also integrates
natively with Vercel for zero-config deployment.

### Why Recharts over D3 or Chart.js?
Recharts is a React-native charting library — charts are React components with props, not
imperative D3 mutations. This integrates cleanly with React's state and data flow. It covers
the chart types needed for this project (line, bar, pie, area) with sensible defaults and
is actively maintained.

---

## 14. Limitations & Future Improvements

### Current limitations

**ETL is not idempotent.** Re-running `silver_to_gold.py` without truncating produces
duplicate key errors. Fix: implement `INSERT … ON CONFLICT DO UPDATE` (upsert) in the
Gold writer, replacing the PySpark JDBC batch insert with per-entity upsert SQL.

**No incremental ingestion.** The ingestion script re-fetches all history on every run.
Fix: record the last ingested timestamp per repo in `pipeline_runs`, then pass
`?since=TIMESTAMP` to the commits/PRs/issues endpoints.

**No scheduling.** The pipeline runs on demand (manual execution). Fix: add an Airflow
DAG or a GitHub Actions workflow on a cron schedule to run nightly ingestion + ETL.

**No data quality layer.** Silver does deduplication but not validation (e.g. commits with
null authors, PRs with impossible dates). Fix: add a Great Expectations or custom rule-based
validation step between Silver and Gold.

**Single-user GitHub token.** The token has a rate limit of 5,000 requests per hour. For
tracking many large repos, this can be exhausted. Fix: rotate between multiple tokens or
use GitHub Apps authentication (15,000 req/hour per installation).

### Possible extensions

- **S3 integration:** replace `data/bronze/` with an S3 bucket and `data/silver/` with S3
  Parquet, turning this into a true cloud-native pipeline
- **Spark on EMR or Databricks:** swap local PySpark for a cloud cluster to handle
  organisation-scale GitHub data (thousands of repos)
- **dbt models:** replace raw SQL views with dbt models for version-controlled, testable
  SQL transformations
- **Real-time layer:** add a GitHub webhook receiver that streams new commits/PRs to a
  Kafka topic, bypassing batch ingestion for near-real-time dashboard updates
- **Authentication:** add OAuth login to the dashboard so each user sees only their own
  tracked repos
