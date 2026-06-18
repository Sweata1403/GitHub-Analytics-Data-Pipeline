"""
AWS Glue ETL Job: Bronze → Silver

Reads raw JSON from S3 Bronze layer, applies cleaning transformations,
and writes optimized Parquet to S3 Silver layer.

Transformations:
  1. Flatten nested JSON structures
  2. Deduplicate by primary key
  3. Cast data types (dates, numbers)
  4. Handle nulls
  5. Partition output by year/month

Deployment:
  Upload this script to S3, then create a Glue ETL job in the AWS Console
  pointing to this script. Use G.1X worker type with 2 workers.

  Required Glue Job Parameters:
    --S3_BUCKET       : S3 bucket name (e.g., github-analytics-data-lake)
    --BRONZE_PREFIX   : Bronze path prefix (default: bronze)
    --SILVER_PREFIX   : Silver path prefix (default: silver)
"""

import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe import DynamicFrame
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    IntegerType,
    LongType,
    BooleanType,
    TimestampType,
    ArrayType,
)


# =====================================================================
# Initialize Glue Context
# =====================================================================

args = getResolvedOptions(sys.argv, [
    "JOB_NAME",
    "S3_BUCKET",
    "BRONZE_PREFIX",
    "SILVER_PREFIX",
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

logger = glueContext.get_logger()

S3_BUCKET = args["S3_BUCKET"]
BRONZE_PREFIX = args.get("BRONZE_PREFIX", "bronze")
SILVER_PREFIX = args.get("SILVER_PREFIX", "silver")


# =====================================================================
# Helper Functions
# =====================================================================

def read_bronze_json(entity_type: str):
    """Read raw JSON from Bronze layer as a Spark DataFrame."""
    path = f"s3://{S3_BUCKET}/{BRONZE_PREFIX}/{entity_type}/"
    logger.info(f"Reading Bronze data from: {path}")

    try:
        df = spark.read.option("multiline", "true").json(path)
        count = df.count()
        logger.info(f"  Loaded {count} records for {entity_type}")
        return df
    except Exception as e:
        logger.warn(f"  No data found for {entity_type}: {e}")
        return None


def write_silver_parquet(df, entity_type: str, partition_cols=None):
    """Write cleaned DataFrame as Parquet to Silver layer."""
    path = f"s3://{S3_BUCKET}/{SILVER_PREFIX}/{entity_type}/"
    logger.info(f"Writing Silver data to: {path}")

    writer = df.write.mode("overwrite")

    if partition_cols:
        writer = writer.partitionBy(*partition_cols)

    writer.parquet(path)

    count = df.count()
    logger.info(f"  Wrote {count} records for {entity_type}")


# =====================================================================
# Entity Transformations
# =====================================================================

def transform_repositories():
    """Clean and transform repository data."""
    df = read_bronze_json("repositories")
    if df is None or df.rdd.isEmpty():
        return

    cleaned = df.select(
        F.col("id").cast(LongType()).alias("github_repo_id"),
        F.col("full_name").cast(StringType()),
        F.col("owner").cast(StringType()),
        F.col("name").cast(StringType()),
        F.col("description").cast(StringType()),
        F.col("language").cast(StringType()),
        F.col("default_branch").cast(StringType()),
        F.col("is_private").cast(BooleanType()),
        F.col("is_fork").cast(BooleanType()),
        F.col("stars_count").cast(IntegerType()),
        F.col("forks_count").cast(IntegerType()),
        F.col("watchers_count").cast(IntegerType()),
        F.col("open_issues_count").cast(IntegerType()),
        F.col("size_kb").cast(IntegerType()),
        F.col("license_name").cast(StringType()),
        F.col("html_url").cast(StringType()),
        F.to_timestamp("created_at").alias("created_at"),
        F.to_timestamp("updated_at").alias("updated_at"),
    ).dropDuplicates(["github_repo_id"])

    # Fill nulls for numeric columns
    cleaned = cleaned.fillna({
        "stars_count": 0,
        "forks_count": 0,
        "watchers_count": 0,
        "open_issues_count": 0,
        "size_kb": 0,
    })

    write_silver_parquet(cleaned, "repositories")
    logger.info("✓ Repositories transformation complete")


def transform_commits():
    """Clean and transform commit data."""
    df = read_bronze_json("commits")
    if df is None or df.rdd.isEmpty():
        return

    cleaned = df.select(
        F.col("sha").cast(StringType()),
        F.col("repository_full_name").cast(StringType()),
        F.col("author_login").cast(StringType()),
        F.col("author_name").cast(StringType()),
        F.col("author_email").cast(StringType()),
        F.to_timestamp("author_date").alias("author_date"),
        F.col("committer_login").cast(StringType()),
        F.col("committer_name").cast(StringType()),
        F.to_timestamp("committer_date").alias("committer_date"),
        F.col("message").cast(StringType()),
        F.col("additions").cast(IntegerType()),
        F.col("deletions").cast(IntegerType()),
        F.col("files_changed").cast(IntegerType()),
    ).dropDuplicates(["sha", "repository_full_name"])

    # Fill nulls
    cleaned = cleaned.fillna({
        "additions": 0,
        "deletions": 0,
        "files_changed": 0,
        "author_name": "Unknown",
    })

    # Add partition columns
    cleaned = cleaned.withColumn("year", F.year("author_date"))
    cleaned = cleaned.withColumn("month", F.month("author_date"))

    # Filter out rows with null dates
    cleaned = cleaned.filter(F.col("author_date").isNotNull())

    write_silver_parquet(cleaned, "commits", partition_cols=["year", "month"])
    logger.info("✓ Commits transformation complete")


def transform_pull_requests():
    """Clean and transform pull request data."""
    df = read_bronze_json("pull_requests")
    if df is None or df.rdd.isEmpty():
        return

    cleaned = df.select(
        F.col("id").cast(LongType()).alias("github_pr_id"),
        F.col("number").cast(IntegerType()),
        F.col("repository_full_name").cast(StringType()),
        F.col("title").cast(StringType()),
        F.col("state").cast(StringType()),
        F.col("author_login").cast(StringType()),
        F.col("draft").cast(BooleanType()),
        F.col("is_merged").cast(BooleanType()),
        F.col("comments_count").cast(IntegerType()),
        F.col("review_comments_count").cast(IntegerType()),
        F.col("commits_count").cast(IntegerType()),
        F.col("additions").cast(IntegerType()),
        F.col("deletions").cast(IntegerType()),
        F.col("changed_files").cast(IntegerType()),
        F.to_timestamp("created_at").alias("created_at"),
        F.to_timestamp("updated_at").alias("updated_at"),
        F.to_timestamp("closed_at").alias("closed_at"),
        F.to_timestamp("merged_at").alias("merged_at"),
    ).dropDuplicates(["github_pr_id", "repository_full_name"])

    # Calculate time-to-merge in hours
    cleaned = cleaned.withColumn(
        "time_to_merge_hours",
        F.when(
            F.col("merged_at").isNotNull(),
            (F.unix_timestamp("merged_at") - F.unix_timestamp("created_at")) / 3600.0
        ).otherwise(None)
    )

    # Fill nulls
    cleaned = cleaned.fillna({
        "comments_count": 0,
        "review_comments_count": 0,
        "commits_count": 0,
        "additions": 0,
        "deletions": 0,
        "changed_files": 0,
        "draft": False,
        "is_merged": False,
    })

    # Add partition columns
    cleaned = cleaned.withColumn("year", F.year("created_at"))
    cleaned = cleaned.withColumn("month", F.month("created_at"))

    cleaned = cleaned.filter(F.col("created_at").isNotNull())

    write_silver_parquet(cleaned, "pull_requests", partition_cols=["year", "month"])
    logger.info("✓ Pull Requests transformation complete")


def transform_issues():
    """Clean and transform issue data."""
    df = read_bronze_json("issues")
    if df is None or df.rdd.isEmpty():
        return

    cleaned = df.select(
        F.col("id").cast(LongType()).alias("github_issue_id"),
        F.col("number").cast(IntegerType()),
        F.col("repository_full_name").cast(StringType()),
        F.col("title").cast(StringType()),
        F.col("state").cast(StringType()),
        F.col("author_login").cast(StringType()),
        F.col("comments_count").cast(IntegerType()),
        F.col("milestone").cast(StringType()),
        F.to_timestamp("created_at").alias("created_at"),
        F.to_timestamp("updated_at").alias("updated_at"),
        F.to_timestamp("closed_at").alias("closed_at"),
    ).dropDuplicates(["github_issue_id", "repository_full_name"])

    # Calculate time-to-close in hours
    cleaned = cleaned.withColumn(
        "time_to_close_hours",
        F.when(
            F.col("closed_at").isNotNull(),
            (F.unix_timestamp("closed_at") - F.unix_timestamp("created_at")) / 3600.0
        ).otherwise(None)
    )

    cleaned = cleaned.fillna({"comments_count": 0})

    # Add partition columns
    cleaned = cleaned.withColumn("year", F.year("created_at"))
    cleaned = cleaned.withColumn("month", F.month("created_at"))

    cleaned = cleaned.filter(F.col("created_at").isNotNull())

    write_silver_parquet(cleaned, "issues", partition_cols=["year", "month"])
    logger.info("✓ Issues transformation complete")


def transform_contributors():
    """Clean and transform contributor data."""
    df = read_bronze_json("contributors")
    if df is None or df.rdd.isEmpty():
        return

    cleaned = df.select(
        F.col("id").cast(LongType()).alias("github_user_id"),
        F.col("login").cast(StringType()),
        F.col("repository_full_name").cast(StringType()),
        F.col("contributions").cast(IntegerType()),
        F.col("avatar_url").cast(StringType()),
        F.col("type").cast(StringType()).alias("user_type"),
        F.col("html_url").cast(StringType()),
    ).dropDuplicates(["github_user_id", "repository_full_name"])

    cleaned = cleaned.fillna({"contributions": 0, "user_type": "User"})

    write_silver_parquet(cleaned, "contributors")
    logger.info("✓ Contributors transformation complete")


def transform_languages():
    """Clean and transform language data."""
    df = read_bronze_json("languages")
    if df is None or df.rdd.isEmpty():
        return

    cleaned = df.select(
        F.col("repository_full_name").cast(StringType()),
        F.col("languages"),  # Map<String, Long>
        F.col("total_bytes").cast(LongType()),
    ).dropDuplicates(["repository_full_name"])

    write_silver_parquet(cleaned, "languages")
    logger.info("✓ Languages transformation complete")


# =====================================================================
# Main Execution
# =====================================================================

logger.info("=" * 60)
logger.info("  Bronze → Silver ETL Starting")
logger.info(f"  Bucket: {S3_BUCKET}")
logger.info(f"  Bronze: {BRONZE_PREFIX}/")
logger.info(f"  Silver: {SILVER_PREFIX}/")
logger.info("=" * 60)

transform_repositories()
transform_commits()
transform_pull_requests()
transform_issues()
transform_contributors()
transform_languages()

logger.info("=" * 60)
logger.info("  Bronze → Silver ETL Complete!")
logger.info("=" * 60)

job.commit()
