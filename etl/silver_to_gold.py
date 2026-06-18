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

import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType


# =====================================================================
# Initialize Glue Context
# =====================================================================

args = getResolvedOptions(sys.argv, [
    "JOB_NAME",
    "S3_BUCKET",
    "SILVER_PREFIX",
    "RDS_CONNECTION_NAME",
    "RDS_DATABASE",
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

logger = glueContext.get_logger()

S3_BUCKET = args["S3_BUCKET"]
SILVER_PREFIX = args.get("SILVER_PREFIX", "silver")
RDS_CONNECTION = args["RDS_CONNECTION_NAME"]
RDS_DATABASE = args["RDS_DATABASE"]


# =====================================================================
# JDBC Connection Properties
# =====================================================================

# Glue resolves JDBC URL from the Connection name
# We get the connection info to build the JDBC URL
connection_options = glueContext.extract_jdbc_conf(RDS_CONNECTION)

JDBC_URL = connection_options.get("fullUrl", "")
JDBC_USER = connection_options.get("user", "")
JDBC_PASSWORD = connection_options.get("password", "")

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
    path = f"s3://{S3_BUCKET}/{SILVER_PREFIX}/{entity_type}/"
    logger.info(f"Reading Silver data from: {path}")
    try:
        df = spark.read.parquet(path)
        count = df.count()
        logger.info(f"  Loaded {count} records for {entity_type}")
        return df
    except Exception as e:
        logger.warn(f"  No data found for {entity_type}: {e}")
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
    write_to_rds(dim, "dim_repository", mode="overwrite")
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

    write_to_rds(dim_user, "dim_user", mode="overwrite")
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

    write_to_rds(fact, "fact_commits", mode="overwrite")
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

    write_to_rds(fact, "fact_pull_requests", mode="overwrite")
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

    write_to_rds(fact, "fact_issues", mode="overwrite")
    logger.info("✓ fact_issues loaded")


def load_repo_languages():
    """Load language breakdown data."""
    df = read_silver_parquet("languages")
    if df is None:
        return

    dim_repo = spark.read.jdbc(JDBC_URL, "dim_repository", properties=jdbc_properties)

    # Explode the languages map into rows
    exploded = df.select(
        F.col("repository_full_name"),
        F.col("total_bytes"),
        F.explode(F.col("languages")).alias("language", "bytes"),
    )

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

    write_to_rds(result, "repo_languages", mode="overwrite")
    logger.info("✓ repo_languages loaded")


# =====================================================================
# Main Execution
# =====================================================================

logger.info("=" * 60)
logger.info("  Silver → Gold (RDS PostgreSQL) ETL Starting")
logger.info(f"  Bucket: {S3_BUCKET}")
logger.info(f"  Silver: {SILVER_PREFIX}/")
logger.info(f"  RDS Connection: {RDS_CONNECTION}")
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

job.commit()
