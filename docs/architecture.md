# Architecture Deep Dive

## Pipeline

```
GitHub REST API
       ↓
Python ingestion (ingestion/ingest.py) — runs locally or on EC2
       ↓
S3 — Bronze layer (raw JSON, one object per entity per repo)
       ↓
Standalone PySpark (etl/bronze_to_silver.py) — runs on your machine, $0
       ↓
S3 — Silver layer (cleaned, typed, deduplicated Parquet)
       ↓
Standalone PySpark (etl/silver_to_gold.py) — runs on your machine, $0
       ↓
RDS PostgreSQL — Gold layer (star schema)
       ↓
FastAPI backend (backend/main.py)
       ↓
Next.js dashboard (dashboard/) — deployed to Vercel
```

## Why no AWS Glue

Glue is a managed Spark environment AWS bills per DPU-hour. For a
personal-scale project (a handful of repos, infrequent runs), that cost buys
nothing local PySpark doesn't already provide: the same `pyspark` library,
same DataFrame API, same Parquet output. `etl/*.py` scripts accept a
`--local` flag to read/write a local `data/` directory, or `--s3-bucket` to
read/write S3 directly via `s3a://` — either way Spark itself runs on your
laptop and AWS never sees a Glue job.

Tradeoff: local PySpark won't scale past your machine's RAM/cores, and
nothing runs on a schedule unless you set up local cron/Task Scheduler (or
move ingestion to EC2 and still trigger the ETL manually/via cron there).
For the data volumes a personal GitHub analytics project produces, this is
not a real constraint.

## Medallion layers

| Layer | Storage | Format | Purpose |
|-------|---------|--------|---------|
| Bronze | S3 | Raw JSON | Exact copy of GitHub API responses, immutable, cheap replay source |
| Silver | S3 | Parquet | Typed, deduplicated, partitioned by year/month where relevant |
| Gold | RDS PostgreSQL | Star schema | Dimensional model built for the dashboard's query patterns |

## Star schema

3 dimensions (`dim_repository`, `dim_user`, `dim_date`) + 3 facts
(`fact_commits`, `fact_pull_requests`, `fact_issues`), plus a supplementary
`repo_languages` table and a `pipeline_runs` audit table. See
[data_dictionary.md](data_dictionary.md) for column-level detail.

## Idempotency

- Bronze: ingestion overwrites the same S3 key per run (no accumulation of
  duplicate raw dumps).
- Silver: PySpark transforms `dropDuplicates` on natural keys (`sha`,
  `github_pr_id`, etc.) and write mode is `overwrite`.
- Gold: fact/dimension tables have `UNIQUE` constraints on the same natural
  keys, so `silver_to_gold.py` can safely upsert on every run.

This means the whole pipeline can be re-run end-to-end at any time without
manual cleanup.
