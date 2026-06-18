"""
Configuration module for the GitHub Analytics Data Pipeline.

Loads environment variables from .env file and provides
typed configuration for all pipeline components.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")


@dataclass
class GitHubConfig:
    """GitHub API configuration."""
    token: str = field(default_factory=lambda: os.getenv("GITHUB_TOKEN", ""))
    usernames: list[str] = field(default_factory=lambda: [
        u.strip() for u in os.getenv("GITHUB_USERNAMES", "").split(",") if u.strip()
    ])
    max_repos_per_user: int = field(
        default_factory=lambda: int(os.getenv("MAX_REPOS_PER_USER", "50"))
    )
    api_base_url: str = "https://api.github.com"
    per_page: int = 100  # Max items per API page


@dataclass
class AWSConfig:
    """AWS configuration."""
    region: str = field(default_factory=lambda: os.getenv("AWS_REGION", "us-east-1"))
    access_key_id: str = field(
        default_factory=lambda: os.getenv("AWS_ACCESS_KEY_ID", "")
    )
    secret_access_key: str = field(
        default_factory=lambda: os.getenv("AWS_SECRET_ACCESS_KEY", "")
    )
    s3_bucket: str = field(
        default_factory=lambda: os.getenv("S3_BUCKET_NAME", "github-analytics-data-lake")
    )


@dataclass
class RDSConfig:
    """RDS PostgreSQL configuration."""
    host: str = field(default_factory=lambda: os.getenv("RDS_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("RDS_PORT", "5432")))
    database: str = field(
        default_factory=lambda: os.getenv("RDS_DATABASE", "github_analytics")
    )
    username: str = field(default_factory=lambda: os.getenv("RDS_USERNAME", "admin"))
    password: str = field(default_factory=lambda: os.getenv("RDS_PASSWORD", ""))

    @property
    def connection_url(self) -> str:
        return (
            f"postgresql://{self.username}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )


@dataclass
class PipelineConfig:
    """Top-level pipeline configuration."""
    github: GitHubConfig = field(default_factory=GitHubConfig)
    aws: AWSConfig = field(default_factory=AWSConfig)
    rds: RDSConfig = field(default_factory=RDSConfig)

    # S3 path prefixes
    bronze_prefix: str = "bronze"
    silver_prefix: str = "silver"
    gold_prefix: str = "gold"

    # Entity types to ingest
    entity_types: list[str] = field(default_factory=lambda: [
        "repositories",
        "commits",
        "pull_requests",
        "issues",
        "contributors",
        "languages",
    ])


# Global config instance
config = PipelineConfig()
