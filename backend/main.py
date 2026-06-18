"""
GitHub Analytics Data Pipeline — FastAPI Backend

Production-ready analytics API serving data from the Gold layer
(RDS PostgreSQL star schema).

Endpoints:
  /api/v1/repositories     — Repository analytics
  /api/v1/commits          — Commit analytics
  /api/v1/pull-requests    — PR analytics
  /api/v1/dashboard        — Aggregated dashboard summary
  /api/v1/health           — Health check

Usage:
  uvicorn main:app --reload --port 8000
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from database import db
from schemas import HealthCheck

load_dotenv()

logger = logging.getLogger(__name__)


# =====================================================================
# Application Lifespan (startup/shutdown)
# =====================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage database connection pool lifecycle."""
    # Startup
    await db.connect()
    logger.info("FastAPI application started")
    yield
    # Shutdown
    await db.disconnect()
    logger.info("FastAPI application shut down")


# =====================================================================
# FastAPI Application
# =====================================================================

app = FastAPI(
    title="GitHub Analytics API",
    description=(
        "Analytics API for the GitHub Analytics Data Pipeline. "
        "Serves insights from a star schema data warehouse powered by "
        "AWS Lakehouse Architecture (Bronze → Silver → Gold)."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
)


# =====================================================================
# CORS Middleware
# =====================================================================

cors_origins = os.getenv("API_CORS_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================================================================
# Register Routers
# =====================================================================

from routers import repositories, commits, pull_requests, dashboard

app.include_router(repositories.router, prefix="/api/v1")
app.include_router(commits.router, prefix="/api/v1")
app.include_router(pull_requests.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")


# =====================================================================
# Root & Health Endpoints
# =====================================================================

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint — API information."""
    return {
        "name": "GitHub Analytics API",
        "version": "1.0.0",
        "docs": "/api/v1/docs",
        "health": "/api/v1/health",
    }


@app.get("/api/v1/health", response_model=HealthCheck, tags=["Health"])
async def health_check():
    """Health check — verifies database connectivity."""
    try:
        await db.fetchval("SELECT 1")
        return HealthCheck(status="healthy", database="connected")
    except Exception as e:
        return HealthCheck(
            status="unhealthy",
            database=f"disconnected: {str(e)}",
        )


# =====================================================================
# Entry Point
# =====================================================================

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info",
    )
