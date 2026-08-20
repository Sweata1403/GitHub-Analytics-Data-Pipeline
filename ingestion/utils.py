"""
Utility functions for the ingestion pipeline.

Provides:
- Structured logging setup
- S3 upload helpers using boto3
- Date/time utilities for partitioning
- Local file storage fallback
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from config import config


# =====================================================================
# Logging
# =====================================================================

def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    Configure structured logging for the pipeline.
    Returns the root logger.
    """
    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
    )
    date_format = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)

    logger = logging.getLogger("github-pipeline")
    logger.info("Logging initialized")
    return logger


# =====================================================================
# Date / Time Utilities
# =====================================================================

def get_current_partition() -> dict[str, str]:
    """
    Get the current date as partition keys for S3 paths.
    Returns: {"year": "2026", "month": "06", "day": "18"}
    """
    now = datetime.now(timezone.utc)
    return {
        "year": now.strftime("%Y"),
        "month": now.strftime("%m"),
        "day": now.strftime("%d"),
    }


def build_s3_key(
    layer: str,
    entity_type: str,
    repo_full_name: str,
    partition: dict[str, str] | None = None,
) -> str:
    """
    Build an S3 object key following the partitioning scheme:
      {layer}/{entity_type}/year={YYYY}/month={MM}/day={DD}/{repo_name}.json

    Args:
        layer: 'bronze', 'silver', or 'gold'
        entity_type: 'repositories', 'commits', etc.
        repo_full_name: 'owner/repo' (slashes replaced with underscores)
        partition: Date partition dict. If None, uses current date.
    """
    if partition is None:
        partition = get_current_partition()

    safe_repo_name = repo_full_name.replace("/", "_")

    return (
        f"{layer}/{entity_type}"
        f"/year={partition['year']}"
        f"/month={partition['month']}"
        f"/day={partition['day']}"
        f"/{safe_repo_name}.json"
    )


# =====================================================================
# S3 Operations
# =====================================================================

def get_s3_client():
    """Create an S3 client using configured credentials."""
    kwargs = {"region_name": config.aws.region}

    if config.aws.access_key_id and config.aws.secret_access_key:
        kwargs["aws_access_key_id"] = config.aws.access_key_id
        kwargs["aws_secret_access_key"] = config.aws.secret_access_key

    return boto3.client("s3", **kwargs)


def upload_to_s3(
    data: list[dict] | dict,
    s3_key: str,
    bucket: str | None = None,
) -> bool:
    """
    Upload JSON data to S3.

    Args:
        data: Data to serialize as JSON and upload.
        s3_key: S3 object key (path within the bucket).
        bucket: S3 bucket name. Defaults to config value.

    Returns:
        True if successful, False otherwise.
    """
    bucket = bucket or config.aws.s3_bucket
    logger = logging.getLogger("github-pipeline.s3")

    try:
        s3 = get_s3_client()
        json_bytes = json.dumps(data, indent=2, default=str).encode("utf-8")

        s3.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=json_bytes,
            ContentType="application/json",
        )

        size_kb = len(json_bytes) / 1024
        logger.info(f"Uploaded s3://{bucket}/{s3_key} ({size_kb:.1f} KB)")
        return True

    except NoCredentialsError:
        logger.error(
            "AWS credentials not found. Set AWS_ACCESS_KEY_ID and "
            "AWS_SECRET_ACCESS_KEY in .env or configure AWS CLI."
        )
        return False

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "NoSuchBucket":
            logger.error(
                f"S3 bucket '{bucket}' does not exist. "
                f"Create it first in the AWS Console."
            )
        else:
            logger.error(f"S3 upload failed: {e}")
        return False


def check_s3_connection(bucket: str | None = None) -> bool:
    """Verify S3 bucket exists and is accessible."""
    bucket = bucket or config.aws.s3_bucket
    logger = logging.getLogger("github-pipeline.s3")

    try:
        s3 = get_s3_client()
        s3.head_bucket(Bucket=bucket)
        logger.info(f"S3 bucket '{bucket}' is accessible")
        return True
    except NoCredentialsError:
        logger.warning("AWS credentials not configured — will use local storage")
        return False
    except ClientError:
        logger.warning(f"S3 bucket '{bucket}' not accessible — will use local storage")
        return False


# =====================================================================
# Local File Storage (Fallback)
# =====================================================================

def save_locally(
    data: list[dict] | dict,
    s3_key: str,
    base_dir: str = "data",
) -> bool:
    """
    Save data to local filesystem (fallback when S3 is not available).
    Mirrors the S3 key structure as local directories.
    """
    logger = logging.getLogger("github-pipeline.local")

    try:
        project_root = Path(__file__).parent.parent
        file_path = project_root / base_dir / s3_key

        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

        size_kb = file_path.stat().st_size / 1024
        logger.info(f"Saved locally: {file_path} ({size_kb:.1f} KB)")
        return True

    except OSError as e:
        logger.error(f"Failed to save locally: {e}")
        return False


def save_data(
    data: list[dict] | dict,
    s3_key: str,
    use_s3: bool = True,
) -> bool:
    """
    Save data to S3 if available, otherwise fall back to local storage.
    """
    if use_s3:
        success = upload_to_s3(data, s3_key)
        if success:
            return True
        # Fall through to local storage

    return save_locally(data, s3_key)


# =====================================================================
# Summary Helpers
# =====================================================================

def format_count(count: int) -> str:
    """Format a number with commas: 1234567 → '1,234,567'."""
    return f"{count:,}"


def format_duration(seconds: float) -> str:
    """Format seconds into human-readable duration."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f}m"
    hours = minutes / 60
    return f"{hours:.1f}h"
