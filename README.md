<p align="center">
  <h1 align="center">📊 GitHub Analytics Data Pipeline</h1>
  <p align="center">
    A production-grade data pipeline that ingests, processes, and visualizes GitHub repository data using AWS Lakehouse Architecture with Medallion pattern.
  </p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/AWS-Lakehouse-FF9900?style=for-the-badge&logo=amazon-aws&logoColor=white" />
  <img src="https://img.shields.io/badge/PySpark-Glue_ETL-E25A1C?style=for-the-badge&logo=apache-spark&logoColor=white" />
  <img src="https://img.shields.io/badge/PostgreSQL-Star_Schema-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/Next.js-Dashboard-000000?style=for-the-badge&logo=next.js&logoColor=white" />
  <img src="https://img.shields.io/badge/Vercel-Deployed-000000?style=for-the-badge&logo=vercel&logoColor=white" />
</p>

---

## 🏗️ Architecture

This pipeline follows the **Medallion Architecture** (Bronze → Silver → Gold):

```
GitHub REST API
       ↓
EC2 (Python Ingestion Layer)
       ↓
S3 (Bronze — Raw JSON)
       ↓
AWS Glue ETL (PySpark)
       ↓
S3 (Silver — Clean Parquet)
       ↓
AWS Glue ETL (PySpark)
       ↓
RDS PostgreSQL (Gold — Star Schema)
       ↓
FastAPI (Backend API)
       ↓
Next.js Dashboard (Vercel)
```

### Data Flow

| Layer | Storage | Format | Purpose |
|-------|---------|--------|---------|
| **Bronze** | S3 | Raw JSON | Exact copy of GitHub API responses |
| **Silver** | S3 | Parquet | Cleaned, deduplicated, typed data |
| **Gold** | RDS PostgreSQL | Star Schema | Analytics-ready dimensional model |

---

## 📁 Project Structure

```
├── ingestion/          # Python scripts to extract data from GitHub API
├── etl/                # AWS Glue PySpark jobs (Bronze→Silver→Gold)
├── database/           # PostgreSQL star schema DDL & migrations
├── backend/            # FastAPI analytics API
├── dashboard/          # Next.js frontend dashboard
├── infrastructure/     # Terraform IaC (reference)
├── scripts/            # Setup, teardown & utility scripts
└── docs/               # Architecture & setup documentation
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- AWS Account (Free Tier eligible)
- GitHub Personal Access Token

### 1. Clone & Configure

```bash
git clone https://github.com/your-username/GitHub-Analytics-Data-Pipeline.git
cd GitHub-Analytics-Data-Pipeline
cp .env.example .env
# Edit .env with your GitHub token and AWS credentials
```

### 2. Run Ingestion

```bash
cd ingestion
pip install -r requirements.txt
python ingest.py
```

### 3. Run ETL (AWS Glue Console)

Upload `etl/bronze_to_silver.py` and `etl/silver_to_gold.py` to AWS Glue and run them.

### 4. Start Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 5. Start Dashboard

```bash
cd dashboard
npm install
npm run dev
```

---

## 📊 Dashboard Preview

The dashboard provides real-time analytics including:

- **Commit Activity Timeline** — Daily/weekly commit patterns
- **Language Distribution** — Breakdown across repositories
- **PR Metrics** — Time-to-merge trends, open vs closed
- **Top Contributors** — Ranked by activity
- **Repository Comparison** — Side-by-side metrics
- **Issue Tracking** — Resolution time & label analysis

---

## 🗄️ Star Schema (Gold Layer)

| Table | Type | Description |
|-------|------|-------------|
| `dim_repository` | Dimension | Repository metadata |
| `dim_user` | Dimension | GitHub user profiles |
| `dim_date` | Dimension | Calendar dimension (2020–2030) |
| `fact_commits` | Fact | Individual commit records |
| `fact_pull_requests` | Fact | Pull request lifecycle data |
| `fact_issues` | Fact | Issue lifecycle data |

---

## 💰 Cost Estimation (AWS)

| Service | Free Tier | Est. Cost |
|---------|-----------|-----------|
| EC2 (t2.micro) | 750 hrs/mo | $0 |
| S3 (< 5 GB) | 5 GB standard | $0 |
| RDS (db.t3.micro) | 750 hrs/mo | $0 |
| Glue ETL | Not free | ~$1.50/run |
| **Vercel** | Free tier | $0 |

> 💡 New AWS accounts get **$200 in credits** — more than enough for development.

---

## 🛑 Stopping Services (Avoid Charges!)

```bash
# Stop all AWS resources when not in use
bash scripts/teardown.sh

# Bring everything back up
bash scripts/startup.sh

# Check current AWS spend
bash scripts/cost_check.sh
```

---

## 📄 Documentation

- [Architecture Deep Dive](docs/architecture.md)
- [AWS Setup Guide (Console)](docs/aws_setup_guide.md)
- [Data Dictionary](docs/data_dictionary.md)

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| Ingestion | Python 3.11, boto3, requests |
| Data Lake | Amazon S3 (JSON, Parquet) |
| ETL | AWS Glue, PySpark |
| Data Warehouse | RDS PostgreSQL 15 |
| Backend API | FastAPI, asyncpg |
| Frontend | Next.js 14, Recharts |
| Deployment | AWS EC2, Vercel |
| IaC | Terraform (reference) |

---

## 📝 License

This project is licensed under the MIT License.
