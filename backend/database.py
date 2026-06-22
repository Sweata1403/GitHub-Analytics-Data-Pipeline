"""
Database connection manager for the FastAPI backend.

Uses asyncpg for high-performance async PostgreSQL access
with connection pooling.
"""

from __future__ import annotations

import os
import logging
from contextlib import asynccontextmanager

import asyncpg
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class Database:
    """Async PostgreSQL connection pool manager."""

    def __init__(self):
        self.pool: asyncpg.Pool | None = None
        self.dsn = self._build_dsn()

    def _build_dsn(self) -> str:
        """Build PostgreSQL connection string from env vars."""
        host = os.getenv("RDS_HOST", "localhost")
        port = os.getenv("RDS_PORT", "5432")
        database = os.getenv("RDS_DATABASE", "github_analytics")
        username = os.getenv("RDS_USERNAME", "admin")
        password = os.getenv("RDS_PASSWORD", "")
        return f"postgresql://{username}:{password}@{host}:{port}/{database}"

    async def connect(self):
        """Initialize connection pool."""
        logger.info("Connecting to PostgreSQL...")
        self.pool = await asyncpg.create_pool(
            dsn=self.dsn,
            min_size=2,
            max_size=10,
            command_timeout=60,
        )
        logger.info("PostgreSQL connection pool established")

    async def disconnect(self):
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("PostgreSQL connection pool closed")

    async def fetch(self, query: str, *args) -> list[dict]:
        """Execute a query and return results as list of dicts."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]

    async def fetchrow(self, query: str, *args) -> dict | None:
        """Execute a query and return a single row as dict."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    async def fetchval(self, query: str, *args):
        """Execute a query and return a single value."""
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    async def execute(self, query: str, *args):
        """Execute a query (INSERT, UPDATE, DELETE)."""
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)


# Global database instance
db = Database()
