# GitHub Analytics Data Pipeline

> An end-to-end data engineering pipeline that ingests GitHub activity via the GitHub API,
> processes it through a **Bronze → Silver → Gold** Medallion architecture using PySpark,
> stores it in a PostgreSQL star schema, and serves it through a FastAPI backend to a
> Next.js analytics dashboard.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![PySpark](https://img.shields.io/badge/PySpark-3.x-E25A1C?logo=apachespark&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=nextdotjs&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-336791?logo=postgresql&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

---

## What This Project Does

This pipeline answers questions like:
- Which repositories are most active?
- Who are the top contributors across all tracked repos?
- How has commit activity trended over time?
- What languages dominate the codebase?
- How are pull requests and issues distributed?

It does this by pulling raw data from the GitHub API, cleaning and deduplicating it with
PySpark, loading it into a relational star schema, exposing it through a REST API, and
rendering it in an interactive dashboard.

---

## Architecture

```
GitHub API
    │
    ▼
┌──────────────────────────────────────────┐
│  INGESTION  (ingestion/ingest.py)        │
│  Repos · Commits · PRs · Issues ·        │
│  Contributors · Languages                │
└──────────────────────────────────────────┘
    │  Raw JSON
    ▼
┌──────────────────────────────────────────┐
│  BRONZE  data/bronze/                    │
│  Hive-partitioned: year=/month=/day=/    │
│  Immutable raw source of truth           │
└──────────────────────────────────────────┘
    │  PySpark ETL
    ▼
┌──────────────────────────────────────────┐
│  SILVER  data/silver/                    │
│  Deduplicated · Type-enforced · Parquet  │
└──────────────────────────────────────────┘
    │  PySpark + JDBC
    ▼
┌──────────────────────────────────────────┐
│  GOLD  PostgreSQL (Star Schema)          │
│  dim_repository · dim_user · dim_date   │
│  fact_commits · fact_pull_requests ·    │
│  fact_issues · repo_languages            │
└──────────────────────────────────────────┘
    │  asyncpg pool
    ▼
┌──────────────────────────────────────────┐
│  BACKEND  FastAPI (backend/)             │
│  REST API · Swagger UI · Health check    │
└──────────────────────────────────────────┘
    │  HTTP
    ▼
┌──────────────────────────────────────────┐
│  DASHBOARD  Next.js + Recharts           │
│  Interactive charts · Live data          │
└──────────────────────────────────────────┘
```

---

## Tech Stack

| Component | Technology |
|---|---|
| Ingestion | Python, GitHub REST API |
| Bronze → Silver | PySpark (deduplication, type enforcement) |
| Silver → Gold | PySpark + JDBC (PostgreSQL) |
| Database | PostgreSQL (star schema / Kimball) |
| Backend API | FastAPI, asyncpg, Pydantic |
| Dashboard | Next.js 16, React 19, Recharts |
| Cloud DB (optional) | AWS RDS PostgreSQL / Neon |
| Backend hosting (optional) | Render |
| Dashboard hosting (optional) | Vercel |

---

## Project Structure

```
GitHub-Analytics-Data-Pipeline/
├── ingestion/          # GitHub API ingestion scripts
├── etl/                # PySpark Bronze→Silver and Silver→Gold jobs
├── database/           # schema.sql + seed_dim_date.sql
├── backend/            # FastAPI app + asyncpg database layer
├── dashboard/          # Next.js + Recharts frontend
├── docs/               # Architecture.md + Runbook.md
│   └── full_documentation.md
├── data/               # Bronze JSON + Silver Parquet (gitignored)
└── .env                # Credentials (gitignored — never commit)
```

---

## Quickstart (Local)

### 1. Clone and configure

```bash
git clone https://github.com/YOUR_USERNAME/GitHub-Analytics-Data-Pipeline.git
cd GitHub-Analytics-Data-Pipeline
cp .env.example .env   # fill in GITHUB_TOKEN and RDS_* values
```

### 2. Set up PostgreSQL

```bash
psql -U postgres -c "CREATE DATABASE github_analytics;"
psql -U postgres -d github_analytics -f database/schema.sql
psql -U postgres -d github_analytics -f database/seed_dim_date.sql
```

### 3. Run the pipeline

```bash
# Ingest from GitHub API
python ingestion/ingest.py --local

# Bronze → Silver
python etl/bronze_to_silver.py

# Truncate Gold tables (required before each ETL run)
psql -U postgres -d github_analytics -c \
  "TRUNCATE TABLE repo_languages, fact_issues, fact_pull_requests, fact_commits, dim_user, dim_repository RESTART IDENTITY CASCADE;"

# Silver → Gold
python etl/silver_to_gold.py
```

### 4. Start backend

```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
# Visit: http://localhost:8000/api/v1/health
# Swagger: http://localhost:8000/api/v1/docs
```

### 5. Start dashboard

```bash
cd dashboard
npm install
npm run dev
# Visit: http://localhost:3000
```

---

## Environment Variables

| Variable | Description |
|---|---|
| `GITHUB_TOKEN` | GitHub fine-grained PAT with repo read permissions |
| `GITHUB_USERNAMES` | Comma-separated list of GitHub usernames to track |
| `RDS_HOST` | PostgreSQL host (`127.0.0.1` for local) |
| `RDS_PORT` | PostgreSQL port (default `5432`) |
| `RDS_DATABASE` | Database name (`github_analytics`) |
| `RDS_USERNAME` | PostgreSQL username |
| `RDS_PASSWORD` | PostgreSQL password |

Dashboard also uses `dashboard/.env.local`:

```
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

---

## Documentation

- [Architecture](docs/Architecture.md) — pipeline design, layer breakdown, design decisions
- [Runbook](docs/Runbook.md) — how to run locally, deploy to cloud, and recover from failures
- [Full Documentation](docs/full_documentation.md) — deep-dive into every component

---

## Windows Users

PySpark on Windows requires `winutils.exe`. See the [Runbook](docs/Runbook.md#pyspark-wont-start-on-windows)
for the exact setup steps.

---

## License

MIT
