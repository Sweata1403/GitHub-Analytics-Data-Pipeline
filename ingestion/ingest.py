"""
Main ingestion orchestrator for the GitHub Analytics Data Pipeline.

This script:
1. Connects to the GitHub API (authenticated)
2. Fetches the user's repositories
3. For each repo, extracts: commits, PRs, issues, contributors, languages
4. Saves raw JSON to S3 Bronze layer (or locally if S3 unavailable)
5. Produces an ingestion summary report

Usage:
    python ingest.py                    # Ingest all repos for configured user
    python ingest.py --local            # Force local storage (skip S3)
    python ingest.py --repos repo1,repo2 # Ingest specific repos only
    python ingest.py --max-repos 10     # Limit number of repos
"""

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timezone

from config import config
from github_client import GitHubClient
from models import (
    Repository,
    Commit,
    PullRequest,
    Issue,
    Contributor,
    LanguageBreakdown,
    IngestionMetadata,
)
from utils import (
    setup_logging,
    build_s3_key,
    save_data,
    check_s3_connection,
    get_current_partition,
    format_count,
    format_duration,
)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="GitHub Analytics Data Pipeline — Ingestion Layer"
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Force local storage (skip S3 upload)",
    )
    parser.add_argument(
        "--repos",
        type=str,
        default=None,
        help="Comma-separated list of specific repos to ingest (owner/repo format)",
    )
    parser.add_argument(
        "--max-repos",
        type=int,
        default=None,
        help="Maximum number of repos to ingest",
    )
    parser.add_argument(
        "--max-commit-pages",
        type=int,
        default=5,
        help="Maximum pages of commits to fetch per repo (100 per page)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser.parse_args()


def ingest_repository(
    client: GitHubClient,
    repo_data: dict,
    partition: dict[str, str],
    use_s3: bool,
    max_commit_pages: int,
    logger,
) -> dict[str, int]:
    """
    Ingest all entity types for a single repository.

    Returns:
        Dict of entity counts: {"commits": 150, "pull_requests": 30, ...}
    """
    full_name = repo_data["full_name"]
    owner, repo_name = full_name.split("/")
    counts = {}

    logger.info(f"{'='*60}")
    logger.info(f"Ingesting: {full_name}")
    logger.info(f"{'='*60}")

    # ---- 1. Repository Details ----
    try:
        repo_model = Repository.from_api(repo_data)
        s3_key = build_s3_key("bronze", "repositories", full_name, partition)
        save_data(repo_model.to_dict(), s3_key, use_s3=use_s3)
        counts["repositories"] = 1
        logger.info(f"  ✓ Repository metadata saved")
    except Exception as e:
        logger.error(f"  ✗ Repository metadata failed: {e}")
        counts["repositories"] = 0

    # ---- 2. Commits ----
    try:
        raw_commits = client.get_repo_commits(
            owner, repo_name, max_pages=max_commit_pages
        )
        commits = [Commit.from_api(c, full_name).to_dict() for c in raw_commits]
        s3_key = build_s3_key("bronze", "commits", full_name, partition)
        save_data(commits, s3_key, use_s3=use_s3)
        counts["commits"] = len(commits)
        logger.info(f"  ✓ Commits: {format_count(len(commits))}")
    except Exception as e:
        logger.error(f"  ✗ Commits failed: {e}")
        counts["commits"] = 0

    # ---- 3. Pull Requests ----
    try:
        raw_prs = client.get_repo_pull_requests(owner, repo_name)
        prs = [PullRequest.from_api(pr, full_name).to_dict() for pr in raw_prs]
        s3_key = build_s3_key("bronze", "pull_requests", full_name, partition)
        save_data(prs, s3_key, use_s3=use_s3)
        counts["pull_requests"] = len(prs)
        logger.info(f"  ✓ Pull Requests: {format_count(len(prs))}")
    except Exception as e:
        logger.error(f"  ✗ Pull Requests failed: {e}")
        counts["pull_requests"] = 0

    # ---- 4. Issues ----
    try:
        raw_issues = client.get_repo_issues(owner, repo_name)
        issues = [Issue.from_api(i, full_name).to_dict() for i in raw_issues]
        s3_key = build_s3_key("bronze", "issues", full_name, partition)
        save_data(issues, s3_key, use_s3=use_s3)
        counts["issues"] = len(issues)
        logger.info(f"  ✓ Issues: {format_count(len(issues))}")
    except Exception as e:
        logger.error(f"  ✗ Issues failed: {e}")
        counts["issues"] = 0

    # ---- 5. Contributors ----
    try:
        raw_contributors = client.get_repo_contributors(owner, repo_name)
        contributors = [
            Contributor.from_api(c, full_name).to_dict() for c in raw_contributors
        ]
        s3_key = build_s3_key("bronze", "contributors", full_name, partition)
        save_data(contributors, s3_key, use_s3=use_s3)
        counts["contributors"] = len(contributors)
        logger.info(f"  ✓ Contributors: {format_count(len(contributors))}")
    except Exception as e:
        logger.error(f"  ✗ Contributors failed: {e}")
        counts["contributors"] = 0

    # ---- 6. Languages ----
    try:
        raw_languages = client.get_repo_languages(owner, repo_name)
        lang_model = LanguageBreakdown.from_api(raw_languages, full_name)
        s3_key = build_s3_key("bronze", "languages", full_name, partition)
        save_data(lang_model.to_dict(), s3_key, use_s3=use_s3)
        counts["languages"] = len(raw_languages)
        logger.info(f"  ✓ Languages: {len(raw_languages)} detected")
    except Exception as e:
        logger.error(f"  ✗ Languages failed: {e}")
        counts["languages"] = 0

    return counts


def main():
    """Main entry point for the ingestion pipeline."""
    args = parse_args()
    logger = setup_logging(args.log_level)

    run_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    logger.info("=" * 70)
    logger.info("  GitHub Analytics Data Pipeline — Ingestion")
    logger.info(f"  Run ID: {run_id}")
    logger.info(f"  Started: {datetime.now(timezone.utc).isoformat()}")
    logger.info("=" * 70)

    # ---- Initialize GitHub Client ----
    client = GitHubClient()

    if not client.check_connection():
        logger.error("Cannot connect to GitHub API. Check your GITHUB_TOKEN.")
        sys.exit(1)

    # ---- Determine S3 vs Local Storage ----
    use_s3 = not args.local
    if use_s3:
        use_s3 = check_s3_connection()
        if not use_s3:
            logger.warning("Falling back to local storage (data/ directory)")

    # ---- Get Target Repositories ----
    if args.repos:
        # Specific repos provided via CLI
        repo_names = [r.strip() for r in args.repos.split(",")]
        repos = []
        for name in repo_names:
            if "/" not in name:
                logger.warning(f"Skipping '{name}' — must be in owner/repo format")
                continue
            owner, repo = name.split("/", 1)
            try:
                repo_data = client.get_repo_details(owner, repo)
                repos.append(repo_data)
            except Exception as e:
                logger.error(f"Failed to fetch repo '{name}': {e}")
    else:
        # Fetch authenticated user's repos
        try:
            user = client.get_authenticated_user()
            username = user["login"]
            logger.info(f"Authenticated as: {username}")
        except Exception:
            logger.error("Failed to get authenticated user. Is GITHUB_TOKEN valid?")
            sys.exit(1)

        max_repos = args.max_repos or config.github.max_repos_per_user
        repos = client.get_user_repos(max_repos=max_repos)
        logger.info(f"Found {len(repos)} repositories for {username}")

        # Also fetch repos for any additional configured usernames
        for extra_user in config.github.usernames:
            if extra_user and extra_user != username:
                try:
                    extra_repos = client.get_user_repos(
                        username=extra_user, max_repos=max_repos
                    )
                    repos.extend(extra_repos)
                    logger.info(
                        f"Found {len(extra_repos)} repositories for {extra_user}"
                    )
                except Exception as e:
                    logger.error(f"Failed to fetch repos for {extra_user}: {e}")

    if not repos:
        logger.warning("No repositories found to ingest. Exiting.")
        sys.exit(0)

    # ---- Run Ingestion ----
    partition = get_current_partition()
    metadata = IngestionMetadata(
        run_id=run_id,
        started_at=datetime.now(timezone.utc).isoformat(),
    )

    total_counts: dict[str, int] = {}
    errors: list[str] = []

    for i, repo_data in enumerate(repos, 1):
        full_name = repo_data.get("full_name", "unknown")
        logger.info(f"\n[{i}/{len(repos)}] Processing {full_name}...")

        try:
            counts = ingest_repository(
                client=client,
                repo_data=repo_data,
                partition=partition,
                use_s3=use_s3,
                max_commit_pages=args.max_commit_pages,
                logger=logger,
            )

            # Accumulate totals
            for entity, count in counts.items():
                total_counts[entity] = total_counts.get(entity, 0) + count

            metadata.repos_processed += 1

        except Exception as e:
            error_msg = f"Failed to process {full_name}: {e}"
            logger.error(error_msg)
            errors.append(error_msg)

    # ---- Save Ingestion Metadata ----
    metadata.completed_at = datetime.now(timezone.utc).isoformat()
    metadata.status = "completed" if not errors else "completed_with_errors"
    metadata.total_entities = total_counts
    metadata.errors = errors

    metadata_key = build_s3_key("bronze", "_metadata", f"run_{run_id}", partition)
    save_data(metadata.to_dict(), metadata_key, use_s3=use_s3)

    # ---- Print Summary ----
    elapsed = time.time() - start_time

    logger.info("\n" + "=" * 70)
    logger.info("  INGESTION COMPLETE")
    logger.info("=" * 70)
    logger.info(f"  Run ID:           {run_id}")
    logger.info(f"  Duration:         {format_duration(elapsed)}")
    logger.info(f"  Repos Processed:  {metadata.repos_processed}/{len(repos)}")
    logger.info(f"  Storage:          {'S3' if use_s3 else 'Local (data/)'}")
    logger.info(f"  Errors:           {len(errors)}")
    logger.info("")
    logger.info("  Entity Totals:")
    for entity, count in sorted(total_counts.items()):
        logger.info(f"    {entity:<20s} {format_count(count):>10s}")
    logger.info("=" * 70)

    if errors:
        logger.warning(f"\n{len(errors)} errors occurred:")
        for err in errors:
            logger.warning(f"  - {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
