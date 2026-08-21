# GitHub Analytics Data Pipeline — Runbook

This runbook covers two modes:

- **Mode A — Local:** PostgreSQL running on your machine, backend on localhost
- **Mode B — Deployed:** PostgreSQL on cloud (AWS RDS or Neon), backend on Render,
  dashboard on Vercel

---

## Prerequisites (both modes)

| Requirement       | Version | Check                              |
| ----------------- | ------- | ---------------------------------- |
| Python            | 3.10+   | `python --version`                 |
| Java (JDK)        | 11+     | `java -version`                    |
| PySpark           | 3.x     | `pip show pyspark`                 |
| Node.js           | 18+     | `node --version`                   |
| PostgreSQL client | any     | `psql --version`                   |
| HADOOP_HOME       | set     | `echo $HADOOP_HOME` (Windows only) |

**Windows only:** `HADOOP_HOME` must point to a folder containing `bin/winutils.exe` and
`bin/hadoop.dll`. If missing, see [Recovery → PySpark won't start on Windows](#pyspark-wont-start-on-windows).

---

## Mode A — Run Fully Local

### Step 1 — Configure environment

Copy `.env.example` to `.env` in the project root and fill in:

```env
GITHUB_TOKEN=ghp_your_token_here
GITHUB_USERNAMES=Sweata1403
MAX_REPOS_PER_USER=50

RDS_HOST=127.0.0.1
RDS_PORT=5432
RDS_DATABASE=github_analytics
RDS_USERNAME=your_pg_username
RDS_PASSWORD=your_pg_password
```

### Step 2 — Set up PostgreSQL database

```bash
# Create the database (run once)
psql -U postgres -c "CREATE DATABASE github_analytics;"

# Load schema (run from project root)
psql -U postgres -d github_analytics -f database/schema.sql

# Seed date dimension (run once)
psql -U postgres -d github_analytics -f database/seed_dim_date.sql

# Verify
psql -U postgres -d github_analytics -c "SELECT COUNT(*) FROM dim_date;"
# Expected: 4018
```

### Step 3 — Ingest data from GitHub

```bash
cd ingestion
python ingest.py --local
```

Flags:

- `--local` — saves JSON to `data/bronze/` instead of S3
- `--max-repos 10` — limit repos per user (useful for testing)
- `--repos owner/repo` — ingest a specific repo only

Expected output: files appear in `data/bronze/{entity}/year=.../month=.../day=.../`

### Step 4 — Bronze → Silver (PySpark)

```bash
python etl/bronze_to_silver.py
```

Expected: Parquet files appear in `data/silver/`. Check counts printed at end of run.

### Step 5 — Silver → Gold (PySpark + JDBC)

**Important:** Always truncate Gold tables before running to avoid duplicate key errors.

```bash
# Truncate first (run from psql or any PostgreSQL client)
psql -U postgres -d github_analytics -c "
TRUNCATE TABLE repo_languages, fact_issues, fact_pull_requests, fact_commits,
               dim_user, dim_repository RESTART IDENTITY CASCADE;
"

# Then run ETL
python etl/silver_to_gold.py
```

Expected: all 6 tables populated. Verify:

```sql
SELECT 'dim_repository' AS t, COUNT(*) FROM dim_repository
UNION ALL SELECT 'dim_user', COUNT(*) FROM dim_user
UNION ALL SELECT 'fact_commits', COUNT(*) FROM fact_commits
UNION ALL SELECT 'fact_pull_requests', COUNT(*) FROM fact_pull_requests
UNION ALL SELECT 'fact_issues', COUNT(*) FROM fact_issues
UNION ALL SELECT 'repo_languages', COUNT(*) FROM repo_languages;
```

### Step 6 — Start FastAPI backend

```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

Verify: open `http://localhost:8000/api/v1/health` — should return:

```json
{ "status": "healthy", "database": "connected", "version": "1.0.0" }
```

Swagger UI: `http://localhost:8000/api/v1/docs`

### Step 7 — Start Next.js dashboard

Make sure `dashboard/.env.local` contains:

```
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

```bash
cd dashboard
npm install
npm run dev
```

Open `http://localhost:3000` — dashboard shows live data.

---

## Mode B — Run with Cloud Deployment

### Cloud stack

- **Database:** AWS RDS PostgreSQL (free tier 12 months) or Neon (always free)
- **Backend:** Render (free tier — spins down after 15 min of inactivity)
- **Dashboard:** Vercel (always free for personal projects)

### Step 1 — Provision cloud database

**Option 1: AWS RDS**

1. AWS Console → RDS → Create database
2. Engine: PostgreSQL, Template: Free tier
3. DB identifier: `github-analytics`, Username: `admin`, Password: letters+numbers only
4. Instance: `db.t3.micro`, Storage: 20 GB
5. **Public access: Yes**
6. Security group: add inbound rule — PostgreSQL (5432) from your IP + from Render IP ranges
7. Wait ~5 min for status to become "Available"
8. Copy the endpoint from RDS dashboard (looks like `github-analytics.xxxx.us-east-1.rds.amazonaws.com`)

**⚠️ Cost reminder:** Stop the RDS instance when not in use.  
AWS Console → RDS → Select instance → Actions → **Stop temporarily**  
(It auto-restarts after 7 days — stop again if needed.)

**Option 2: Neon**

1. Go to console.neon.tech → New project → `github-analytics` → US East 2 → Create
2. From project dashboard click **Connect** → copy the connection string
3. Neon scales to zero automatically — no manual stopping needed

### Step 2 — Load schema to cloud database

```bash
# AWS RDS
psql "postgresql://admin:PASSWORD@YOUR_RDS_ENDPOINT:5432/github_analytics" \
  -f database/schema.sql
psql "postgresql://admin:PASSWORD@YOUR_RDS_ENDPOINT:5432/github_analytics" \
  -f database/seed_dim_date.sql

# Neon
psql "postgresql://USER:PASSWORD@HOST/neondb?sslmode=require" < database/schema.sql
psql "postgresql://USER:PASSWORD@HOST/neondb?sslmode=require" < database/seed_dim_date.sql
```

### Step 3 — Update .env to point at cloud database

```env
RDS_HOST=your-rds-endpoint.rds.amazonaws.com   # or Neon host
RDS_PORT=5432
RDS_DATABASE=github_analytics                   # or neondb for Neon
RDS_USERNAME=admin
RDS_PASSWORD=your_password
```

### Step 4 — Run ETL against cloud database

```bash
# Truncate cloud Gold tables first
psql "postgresql://USER:PASSWORD@HOST/DB" -c "
TRUNCATE TABLE repo_languages, fact_issues, fact_pull_requests, fact_commits,
               dim_user, dim_repository RESTART IDENTITY CASCADE;
"

# Run Silver → Gold (JDBC will write directly to cloud DB)
python etl/silver_to_gold.py
```

> Bronze → Silver still runs locally (Parquet stays in `data/silver/`). Only the Gold
> write goes to the cloud database.

### Step 5 — Deploy backend to Render

1. Push your code to GitHub (make sure `.env` is in `.gitignore` — never commit credentials)
2. Go to render.com → New → Web Service → connect your GitHub repo
3. Settings:
   - Root directory: `backend`
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Environment variables — add each from your `.env`:
   - `RDS_HOST`, `RDS_PORT`, `RDS_DATABASE`, `RDS_USERNAME`, `RDS_PASSWORD`
5. Click **Deploy** — wait ~2 min
6. Copy your Render URL (e.g. `https://github-analytics-api.onrender.com`)
7. Test: `https://your-render-url.onrender.com/api/v1/health`

### Step 6 — Deploy dashboard to Vercel

1. Go to vercel.com → New Project → import your GitHub repo
2. Set root directory to `dashboard`
3. Environment variable:
   - `NEXT_PUBLIC_API_URL` = `https://your-render-url.onrender.com/api/v1`
4. Click Deploy — Vercel gives you a public URL instantly

---

## Recovery Procedures

### PostgreSQL connection fails (socket error / getaddrinfo failed)

**Symptom:** `socket.gaierror: [Errno 11003] getaddrinfo failed` or similar DNS error  
**Cause:** Special characters (`@`, `:`, `/`) in the password break the `postgresql://` URL  
**Fix:** In `backend/database.py`, ensure credentials are URL-encoded:

```python
from urllib.parse import quote_plus
username = quote_plus(os.getenv("RDS_USERNAME", "admin"))
password = quote_plus(os.getenv("RDS_PASSWORD", ""))
return f"postgresql://{username}:{password}@{host}:{port}/{database}"
```

---

### duplicate key value violates unique constraint

**Symptom:** `ERROR: duplicate key value violates unique constraint "dim_repository_github_repo_id_key"`  
**Cause:** `silver_to_gold.py` uses `mode="append"` — running it twice inserts the same rows twice  
**Fix:** Always truncate Gold tables before re-running the ETL:

```sql
TRUNCATE TABLE repo_languages, fact_issues, fact_pull_requests, fact_commits,
               dim_user, dim_repository RESTART IDENTITY CASCADE;
```

---

### cannot drop table … because other objects depend on it

**Symptom:** FK constraint error during ETL  
**Cause:** Old code used `mode="overwrite"` which tries to DROP and recreate tables, but
views and FK references block the DROP  
**Fix:** All `mode=` in `silver_to_gold.py` must be `"append"`, not `"overwrite"`. Truncate manually before each run.

---

### Cannot resolve "explode(languages)" — STRUCT type error

**Symptom:** `requires ARRAY or MAP type, however "languages" has type STRUCT<Apex: BIGINT, C: BIGINT, ...>`  
**Cause:** Parquet infers `languages` as a STRUCT (one field per language) instead of a MAP  
**Fix:** In `silver_to_gold.py`, dynamically convert struct to map before exploding:

```python
struct_fields = df.schema["languages"].dataType.fields
map_col = F.create_map(*[
    item for f in struct_fields for item in (F.lit(f.name), F.col("languages")[f.name])
])
exploded = df.select(
    F.col("repository_full_name"),
    F.col("total_bytes"),
    F.explode(map_col).alias("language", "bytes"),
).filter(F.col("bytes").isNotNull())
```

---

### PySpark won't start on Windows

**Symptom:** `java.io.FileNotFoundException: HADOOP_HOME and hadoop.home.dir are unset`  
or `UnsatisfiedLinkError: hadoop.dll`  
**Fix:**

```cmd
# 1. Download winutils.exe + hadoop.dll from:
#    https://github.com/cdarlint/winutils/tree/master/hadoop-3.3.6/bin

# 2. Create C:\hadoop\bin\ and put both files there

# 3. Set environment variable (run as admin in cmd.exe)
setx HADOOP_HOME "C:\hadoop"

# 4. Copy hadoop.dll to System32
copy C:\hadoop\bin\hadoop.dll C:\Windows\System32\hadoop.dll

# 5. Restart your terminal and try again
```

---

### uvicorn or pip not found

**Symptom:** `uvicorn: command not found` or `pip: command not found`  
**Fix:** Use the module form — Python finds it even when the PATH entry is missing:

```bash
python -m uvicorn main:app --reload --port 8000
python -m pip install -r requirements.txt
```

---

### Render backend returns 502 / takes 30+ seconds to respond

**Cause:** Render free tier spins down after 15 minutes of inactivity. First request after
sleep wakes it up — this takes 20–30 seconds.  
**Fix:** This is normal on free tier. For production, upgrade to a paid instance or use a
cron job to ping `/api/v1/health` every 10 minutes to keep it warm.

---

### AWS RDS — forgot to stop instance

**Cost risk:** RDS free tier gives 750 hours/month. If you leave it running 24/7 it uses all
750 hours in ~31 days (exactly free tier limit). A second instance running simultaneously
would start billing.  
**Fix:** Stop the instance immediately:  
AWS Console → RDS → Instances → select `github-analytics` → Actions → **Stop temporarily**

**⚠️ Set a reminder:** RDS automatically restarts after 7 days. Stop it again each time.

---

## Quick Reference — Common Commands

```bash
# Full local pipeline from scratch
psql -U postgres -d github_analytics -f database/schema.sql
psql -U postgres -d github_analytics -f database/seed_dim_date.sql
python ingestion/ingest.py --local
python etl/bronze_to_silver.py
psql -U postgres -d github_analytics -c "TRUNCATE TABLE repo_languages, fact_issues, fact_pull_requests, fact_commits, dim_user, dim_repository RESTART IDENTITY CASCADE;"
python etl/silver_to_gold.py
cd backend && python -m uvicorn main:app --reload --port 8000
cd dashboard && npm run dev

# Health check
curl http://localhost:8000/api/v1/health

# Count rows in Gold tables
psql -U postgres -d github_analytics -c "SELECT 'dim_repository' AS t, COUNT(*) FROM dim_repository UNION ALL SELECT 'fact_commits', COUNT(*) FROM fact_commits;"

# Stop AWS RDS (run in AWS CLI if configured)
aws rds stop-db-instance --db-instance-identifier github-analytics
```
