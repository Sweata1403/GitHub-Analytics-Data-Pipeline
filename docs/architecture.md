# GitHub Analytics Data Pipeline — Architecture

## Overview

This project is a full-stack data engineering pipeline that ingests GitHub activity data,
processes it through a three-layer Medallion architecture, stores it in a relational star
schema, and serves it through a FastAPI backend to a Next.js dashboard.

---

## High-Level Architecture

```
GitHub API
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│                   INGESTION LAYER                        │
│  ingestion/ingest.py                                     │
│  • Authenticates via GitHub PAT                          │
│  • Fetches repos, commits, PRs, issues,                  │
│    contributors, languages per repo                      │
│  • Saves raw JSON → data/bronze/  (or S3)                │
└─────────────────────────────────────────────────────────┘
    │
    ▼  raw JSON (Hive-partitioned: year=/month=/day=/)
┌─────────────────────────────────────────────────────────┐
│                   BRONZE LAYER                           │
│  data/bronze/{entity}/year=YYYY/month=MM/day=DD/*.json  │
│  • Immutable raw source of truth                         │
│  • Never modified after write                            │
└─────────────────────────────────────────────────────────┘
    │
    ▼  PySpark ETL
┌─────────────────────────────────────────────────────────┐
│                   SILVER LAYER                           │
│  etl/bronze_to_silver.py  →  data/silver/*.parquet       │
│  • Schema enforcement (type casting)                     │
│  • Deduplication via dropDuplicates()                    │
│  • Stored as Parquet (columnar, compressed)              │
└─────────────────────────────────────────────────────────┘
    │
    ▼  PySpark + JDBC ETL
┌─────────────────────────────────────────────────────────┐
│                   GOLD LAYER                             │
│  etl/silver_to_gold.py  →  PostgreSQL (Star Schema)      │
│  • Resolves surrogate keys via JDBC joins                │
│  • Loads dimension + fact tables                         │
│  • Supports local PostgreSQL or cloud RDS/Neon           │
└─────────────────────────────────────────────────────────┘
    │
    ▼  asyncpg connection pool
┌─────────────────────────────────────────────────────────┐
│                   BACKEND (FastAPI)                      │
│  backend/main.py                                         │
│  • 4 routers: repositories, commits, pull_requests,      │
│    dashboard                                             │
│  • Async PostgreSQL via asyncpg pool (min 2, max 10)     │
│  • Swagger UI at /api/v1/docs                            │
│  • Health check at /api/v1/health                        │
└─────────────────────────────────────────────────────────┘
    │
    ▼  HTTP (NEXT_PUBLIC_API_URL)
┌─────────────────────────────────────────────────────────┐
│                   DASHBOARD (Next.js)                    │
│  dashboard/                                              │
│  • Next.js 16 + React 19                                 │
│  • Recharts for visualisations                           │
│  • Reads NEXT_PUBLIC_API_URL from .env.local             │
└─────────────────────────────────────────────────────────┘
```

---

## Medallion Architecture Detail

### Bronze Layer — Raw Ingestion

- **Location:** `data/bronze/{entity}/year=YYYY/month=MM/day=DD/`
- **Format:** JSON (one file per API response)
- **Partitioning:** Hive-style date partitioning enables partition pruning — Spark
  only reads the folders it needs instead of scanning everything
- **Entities:** repositories, commits, pull_requests, issues, contributors, languages
- **Rule:** Never modify bronze files. They are the audit trail.

### Silver Layer — Cleaned & Deduplicated

- **Location:** `data/silver/`
- **Format:** Parquet (columnar, Snappy-compressed)
- **Transformations:**
  - Type casting (e.g. string timestamps → TimestampType)
  - `dropDuplicates()` on natural keys (e.g. commit SHA)
  - Null handling
- **Result example:** 2,662 raw commits → 874 after deduplication

### Gold Layer — Star Schema in PostgreSQL

- **Dimension tables:** `dim_repository`, `dim_user`, `dim_date`
- **Fact tables:** `fact_commits`, `fact_pull_requests`, `fact_issues`
- **Supporting:** `repo_languages`, `pipeline_runs`
- **Views:** `v_repository_overview`, `v_daily_commit_activity`, `v_pr_metrics`,
  `v_top_contributors`
- **Surrogate keys:** integer PKs managed by PostgreSQL sequences; ETL resolves them
  via JDBC lookups before inserting fact rows

---

## Database Schema (Star Schema / Kimball)

```
          dim_date
             │
dim_user ────┤
             │
     dim_repository
             │
    ┌────────┼────────┐
    │        │        │
fact_commits  fact_pull_requests  fact_issues
```

**Why star schema?**  
Flat, denormalised joins. A single join from any fact table to its dimension gives you
all descriptive attributes. This is optimised for analytical (OLAP) queries, not
transactional (OLTP) writes.

---

## Technology Stack

| Layer           | Technology                   | Why                                                    |
| --------------- | ---------------------------- | ------------------------------------------------------ |
| Ingestion       | Python + PyGitHub / requests | Simple REST client for GitHub API                      |
| Bronze → Silver | PySpark                      | Handles deduplication and type enforcement at scale    |
| Silver → Gold   | PySpark + JDBC               | Reads Parquet, resolves keys, writes to PostgreSQL     |
| Database        | PostgreSQL                   | ACID compliance, views, FK constraints                 |
| Backend         | FastAPI + asyncpg            | Async, high-performance, auto-generates OpenAPI docs   |
| Dashboard       | Next.js + Recharts           | React-based, server + client components, chart library |

---

## Key Design Decisions

### Why URL-encode credentials in the DSN?

`urllib.parse.quote_plus()` is applied to the username and password before building the
`postgresql://user:pass@host/db` connection string. Without it, special characters like
`@`, `:`, or `/` inside the password break URL parsing — the parser mistakes part of the
password for the host or port.

### Why asyncpg connection pooling?

Creating a new database connection per HTTP request is expensive (~50–100ms). A pool of
2–10 persistent connections is reused across requests, reducing latency and PostgreSQL
server load.

### Why Parquet for Silver?

Parquet is columnar — reading only the columns you need is far faster than row-based
formats like CSV or JSON. It also stores schema metadata, so Spark knows types without
inference. Snappy compression keeps file sizes small.

### Known limitation — idempotency

The ETL uses `mode="append"` to avoid breaking FK constraints from views. This means
re-running `silver_to_gold.py` without first truncating the Gold tables produces
duplicate key violations. The workaround is a manual `TRUNCATE … RESTART IDENTITY CASCADE`
before each ETL run. A production fix would use `INSERT … ON CONFLICT DO UPDATE` (upsert).

---

## Environment Variables

### Root `.env` (used by ingestion + ETL)

```
GITHUB_TOKEN=
GITHUB_USERNAMES=
MAX_REPOS_PER_USER=

RDS_HOST=
RDS_PORT=5432
RDS_DATABASE=github_analytics
RDS_USERNAME=
RDS_PASSWORD=
```

### `dashboard/.env.local` (used by Next.js)

```
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1   # local
# NEXT_PUBLIC_API_URL=https://your-app.onrender.com/api/v1  # deployed
```

---

## Repository Structure

```
GitHub-Analytics-Data-Pipeline/
├── ingestion/
│   ├── config.py          # Typed config dataclasses from .env
│   └── ingest.py          # GitHub API ingestion orchestrator
├── etl/
│   ├── bronze_to_silver.py
│   ├── silver_to_gold.py
│   └── postgresql-42.6.0.jar   # JDBC driver for PySpark → PostgreSQL
├── database/
│   ├── schema.sql          # Full DDL: tables + views
│   └── seed_dim_date.sql   # Populates dim_date 2020–2030
├── backend/
│   ├── main.py             # FastAPI app + lifespan + CORS
│   ├── database.py         # asyncpg pool manager
│   ├── routers/            # repositories, commits, pull_requests, dashboard
│   └── requirements.txt
├── dashboard/
│   ├── app/                # Next.js app router pages
│   ├── components/         # Chart and UI components
│   ├── .env.local          # NEXT_PUBLIC_API_URL
│   └── package.json
├── data/
│   ├── bronze/             # Raw JSON (gitignored)
│   └── silver/             # Parquet (gitignored)
├── docs/
│   ├── Architecture.md     # This file
│   └── Runbook.md
└── .env                    # Credentials (gitignored — never commit this)
```
