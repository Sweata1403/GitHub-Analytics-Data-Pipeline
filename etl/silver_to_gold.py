"""
AWS Glue ETL Job: Silver → Gold (RDS PostgreSQL)

Reads cleaned Parquet from S3 Silver layer, transforms data into
star schema format, and loads it into RDS PostgreSQL (Gold layer).

This job:
  1. Reads Silver Parquet data
  2. Builds dimension tables (dim_repository, dim_user)
  3. Maps fact records to dimension keys
  4. Writes to PostgreSQL using JDBC with upsert logic

Deployment:
  Upload this script to S3, then create a Glue ETL job in the AWS Console.
  Create a Glue JDBC Connection to your RDS PostgreSQL instance first.

  Required Glue Job Parameters:
    --S3_BUCKET            : S3 bucket name
    --SILVER_PREFIX        : Silver path prefix (default: silver)
    --RDS_CONNECTION_NAME  : Glue JDBC connection name for RDS
    --RDS_DATABASE         : PostgreSQL database name
"""

import os
import sys
import argparse
import logging
from dotenv import load_dotenv
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType


# =====================================================================
# Initialize Glue Context
# =====================================================================

# Load .env file from project root
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

def parse_args():
    parser = argparse.ArgumentParser(description="Standalone PySpark Job: Silver -> Gold")
    parser.add_argument("--s3-bucket", type=str, default=None, help="S3 bucket name (not required if local)")
    parser.add_argument("--silver-prefix", type=str, default="silver", help="Silver path prefix")
    parser.add_argument("--local", action="store_true", help="Run in local directory mode")
    parser.add_argument("--rds-host", type=str, default=os.getenv("RDS_HOST", "localhost"), help="PostgreSQL host")
    parser.add_argument("--rds-port", type=str, default=os.getenv("RDS_PORT", "5432"), help="PostgreSQL port")
    parser.add_argument("--rds-database", type=str, default=os.getenv("RDS_DATABASE", "github_analytics"), help="PostgreSQL database")
    parser.add_argument("--rds-username", type=str, default=os.getenv("RDS_USERNAME", "admin"), help="PostgreSQL user")
    parser.add_argument("--rds-password", type=str, default=os.getenv("RDS_PASSWORD", ""), help="PostgreSQL password")
    return parser.parse_args()

args = parse_args()

# Configure structured logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("silver-to-gold")

# Set HADOOP_HOME fallback for Windows if not present
if "HADOOP_HOME" not in os.environ:
    os.environ["HADOOP_HOME"] = str(PROJECT_ROOT)

JAR_PATH = str(PROJECT_ROOT / "etl" / "postgresql-42.6.0.jar")

# Start Spark session
spark = SparkSession.builder \
    .appName("Silver-to-Gold-ETL") \
    .config("spark.jars", JAR_PATH) \
    .config("spark.driver.extraClassPath", JAR_PATH) \
    .config("spark.sql.parquet.datetimeRebaseModeInWrite", "CORRECTED") \
    .config("spark.sql.parquet.datetimeRebaseModeInRead", "CORRECTED") \
    .getOrCreate()

LOCAL_MODE = args.local
S3_BUCKET = args.s3_bucket
SILVER_PREFIX = args.silver_prefix

if not LOCAL_MODE and not S3_BUCKET:
    logger.error("Error: --s3-bucket is required unless running with --local flag")
    sys.exit(1)

# =====================================================================
# JDBC Connection Properties
# =====================================================================

JDBC_URL = f"jdbc:postgresql://{args.rds_host}:{args.rds_port}/{args.rds_database}"
JDBC_USER = args.rds_username
JDBC_PASSWORD = args.rds_password

jdbc_properties = {
    "user": JDBC_USER,
    "password": JDBC_PASSWORD,
    "driver": "org.postgresql.Driver",
}

logger.info(f"JDBC URL: {JDBC_URL}")


# =====================================================================
# Helper Functions
# =====================================================================

def read_silver_parquet(entity_type: str):
    """Read cleaned Parquet from Silver layer."""
    if LOCAL_MODE:
        path = f"data/{SILVER_PREFIX}/{entity_type}/"
    else:
        path = f"s3a://{S3_BUCKET}/{SILVER_PREFIX}/{entity_type}/"

    logger.info(f"Reading Silver data from: {path}")
    try:
        df = spark.read.parquet(path)
        count = df.count()
        logger.info(f"  Loaded {count} records for {entity_type}")
        return df
    except Exception as e:
        logger.warning(f"  No data found for {entity_type}: {e}")
        return None


def write_to_rds(df, table_name: str, mode: str = "append"):
    """Write DataFrame to RDS PostgreSQL via JDBC."""
    logger.info(f"Writing to RDS table: {table_name}")
    try:
        df.write.jdbc(
            url=JDBC_URL,
            table=table_name,
            mode=mode,
            properties=jdbc_properties,
        )
        logger.info(f"  ✓ Wrote {df.count()} rows to {table_name}")
    except Exception as e:
        logger.error(f"  ✗ Failed to write to {table_name}: {e}")
        raise


def date_to_id(date_col):
    """Convert a timestamp column to date_id (YYYYMMDD integer)."""
    return F.date_format(date_col, "yyyyMMdd").cast(IntegerType())


# =====================================================================
# Dimension Loading
# =====================================================================

def load_dim_repository():
    """Load repository dimension from Silver data."""
    df = read_silver_parquet("repositories")
    if df is None:
        return

    dim = df.select(
        F.col("github_repo_id"),
        F.col("full_name"),
        F.col("owner"),
        F.col("name"),
        F.col("description"),
        F.col("language"),
        F.col("default_branch"),
        F.col("is_private"),
        F.col("is_fork"),
        F.col("stars_count"),
        F.col("forks_count"),
        F.col("watchers_count"),
        F.col("open_issues_count"),
        F.col("size_kb"),
        F.col("license_name"),
        F.col("html_url"),
        F.col("created_at"),
        F.col("updated_at"),
        F.current_timestamp().alias("etl_loaded_at"),
    )

    # Use overwrite for dimensions (SCD Type 1 — full refresh)
    write_to_rds(dim, "dim_repository", mode="append")
    logger.info("✓ dim_repository loaded")


def load_dim_user():
    """
    Load user dimension from Silver contributor + commit data.
    Merges users from multiple entity sources.
    """
    users = []

    # From contributors
    contributors_df = read_silver_parquet("contributors")
    if contributors_df is not None:
        contrib_users = contributors_df.select(
            F.col("github_user_id"),
            F.col("login"),
            F.col("avatar_url"),
            F.col("user_type"),
            F.col("html_url"),
        )
        users.append(contrib_users)

    # From commits (author_login)
    commits_df = read_silver_parquet("commits")
    if commits_df is not None:
        commit_users = commits_df.select(
            F.lit(None).cast("long").alias("github_user_id"),
            F.col("author_login").alias("login"),
            F.lit(None).cast("string").alias("avatar_url"),
            F.lit("User").alias("user_type"),
            F.lit(None).cast("string").alias("html_url"),
        ).filter(F.col("login").isNotNull())
        users.append(commit_users)

    if not users:
        logger.warn("No user data found")
        return

    # Union all user sources and deduplicate
    from functools import reduce
    all_users = reduce(lambda a, b: a.unionByName(b), users)
    dim_user = all_users.dropDuplicates(["login"])
    dim_user = dim_user.withColumn("etl_loaded_at", F.current_timestamp())

    write_to_rds(dim_user, "dim_user", mode="append")
    logger.info("✓ dim_user loaded")


# =====================================================================
# Fact Loading
# =====================================================================

def load_fact_commits():
    """Load commit facts, resolving dimension keys."""
    df = read_silver_parquet("commits")
    if df is None:
        return

    # Read dimension tables back from RDS to get surrogate keys
    dim_repo = spark.read.jdbc(JDBC_URL, "dim_repository", properties=jdbc_properties)
    dim_user = spark.read.jdbc(JDBC_URL, "dim_user", properties=jdbc_properties)

    # Join to resolve foreign keys
    fact = (
        df
        .join(
            dim_repo.select("repository_id", "full_name"),
            df.repository_full_name == dim_repo.full_name,
            "left"
        )
        .join(
            dim_user.select(F.col("user_id").alias("author_id"), F.col("login").alias("author_login_dim")),
            df.author_login == F.col("author_login_dim"),
            "left"
        )
        .select(
            F.col("sha"),
            F.col("repository_id"),
            F.col("author_id"),
            F.lit(None).cast(IntegerType()).alias("committer_id"),
            date_to_id(F.col("author_date")).alias("date_id"),
            F.col("message"),
            F.col("additions"),
            F.col("deletions"),
            F.col("files_changed"),
            F.col("author_date").alias("authored_at"),
        )
    )

    write_to_rds(fact, "fact_commits", mode="append")
    logger.info("✓ fact_commits loaded")


def load_fact_pull_requests():
    """Load pull request facts, resolving dimension keys."""
    df = read_silver_parquet("pull_requests")
    if df is None:
        return

    dim_repo = spark.read.jdbc(JDBC_URL, "dim_repository", properties=jdbc_properties)
    dim_user = spark.read.jdbc(JDBC_URL, "dim_user", properties=jdbc_properties)

    fact = (
        df
        .join(
            dim_repo.select("repository_id", "full_name"),
            df.repository_full_name == dim_repo.full_name,
            "left"
        )
        .join(
            dim_user.select(F.col("user_id").alias("author_id"), F.col("login").alias("author_login_dim")),
            df.author_login == F.col("author_login_dim"),
            "left"
        )
        .select(
            F.col("github_pr_id"),
            F.col("number"),
            F.col("repository_id"),
            F.col("author_id"),
            date_to_id(F.col("created_at")).alias("created_date_id"),
            date_to_id(F.col("merged_at")).alias("merged_date_id"),
            date_to_id(F.col("closed_at")).alias("closed_date_id"),
            F.col("title"),
            F.col("state"),
            F.col("is_merged"),
            F.col("draft").alias("is_draft"),
            F.col("comments_count"),
            F.col("review_comments_count"),
            F.col("commits_count"),
            F.col("additions"),
            F.col("deletions"),
            F.col("changed_files"),
            F.col("created_at"),
            F.col("merged_at"),
            F.col("closed_at"),
            F.col("time_to_merge_hours"),
        )
    )

    write_to_rds(fact, "fact_pull_requests", mode="append")
    logger.info("✓ fact_pull_requests loaded")


def load_fact_issues():
    """Load issue facts, resolving dimension keys."""
    df = read_silver_parquet("issues")
    if df is None:
        return

    dim_repo = spark.read.jdbc(JDBC_URL, "dim_repository", properties=jdbc_properties)
    dim_user = spark.read.jdbc(JDBC_URL, "dim_user", properties=jdbc_properties)

    fact = (
        df
        .join(
            dim_repo.select("repository_id", "full_name"),
            df.repository_full_name == dim_repo.full_name,
            "left"
        )
        .join(
            dim_user.select(F.col("user_id").alias("author_id"), F.col("login").alias("author_login_dim")),
            df.author_login == F.col("author_login_dim"),
            "left"
        )
        .select(
            F.col("github_issue_id"),
            F.col("number"),
            F.col("repository_id"),
            F.col("author_id"),
            date_to_id(F.col("created_at")).alias("created_date_id"),
            date_to_id(F.col("closed_at")).alias("closed_date_id"),
            F.col("title"),
            F.col("state"),
            F.col("comments_count"),
            F.col("milestone"),
            F.col("created_at"),
            F.col("closed_at"),
            F.col("time_to_close_hours"),
        )
    )

    write_to_rds(fact, "fact_issues", mode="append")
    logger.info("✓ fact_issues loaded")


def load_repo_languages():
    """Load language breakdown data."""
    df = read_silver_parquet("languages")
    if df is None:
        return

    dim_repo = spark.read.jdbc(JDBC_URL, "dim_repository", properties=jdbc_properties)

    # NOTE: Spark's JSON schema inference merges the varying per-repo language
    # keys (JS/HTML for one repo, Python/Dockerfile for another) into one
    # fixed STRUCT with a field per distinct language name ever seen, rather
    # than a MapType. explode() requires ARRAY/MAP, so we rebuild a proper
    # key -> value map from the struct's fields before exploding.
    struct_fields = df.schema["languages"].dataType.fields
    map_col = F.create_map(*[
        item for f in struct_fields for item in (F.lit(f.name), F.col("languages")[f.name])
    ])

    exploded = df.select(
        F.col("repository_full_name"),
        F.col("total_bytes"),
        F.explode(map_col).alias("language", "bytes"),
    ).filter(F.col("bytes").isNotNull())  # drop languages a given repo doesn't have

    # Calculate percentage
    exploded = exploded.withColumn(
        "percentage",
        F.when(F.col("total_bytes") > 0, F.col("bytes") / F.col("total_bytes") * 100).otherwise(0)
    )

    # Join with dim_repo
    result = (
        exploded
        .join(
            dim_repo.select("repository_id", "full_name"),
            exploded.repository_full_name == dim_repo.full_name,
            "left"
        )
        .select(
            F.col("repository_id"),
            F.col("language"),
            F.col("bytes"),
            F.col("percentage"),
        )
    )

    write_to_rds(result, "repo_languages", mode="append")
    logger.info("✓ repo_languages loaded")


# =====================================================================
# Main Execution
# =====================================================================

logger.info("=" * 60)
logger.info("  Silver → Gold (RDS PostgreSQL) ETL Starting")
logger.info(f"  Bucket: {S3_BUCKET}")
logger.info(f"  Silver: {SILVER_PREFIX}/")
logger.info(f"  RDS Connection: {JDBC_URL}")
logger.info("=" * 60)

# Load dimensions first (facts depend on them)
load_dim_repository()
load_dim_user()

# Then load facts
load_fact_commits()
load_fact_pull_requests()
load_fact_issues()
load_repo_languages()

logger.info("=" * 60)
logger.info("  Silver → Gold ETL Complete!")
logger.info("=" * 60)

spark.stop()