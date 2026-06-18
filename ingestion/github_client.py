"""
GitHub REST API client with automatic rate-limit handling,
pagination, and exponential backoff.
"""

import time
import logging
from typing import Any, Generator

import requests

from config import config

logger = logging.getLogger(__name__)


class GitHubClientError(Exception):
    """Custom exception for GitHub API errors."""
    pass


class RateLimitExceeded(GitHubClientError):
    """Raised when the GitHub API rate limit is exhausted."""
    pass


class GitHubClient:
    """
    GitHub REST API client.

    Features:
    - Authenticated requests (5,000 req/hr with PAT)
    - Automatic pagination (follows Link headers)
    - Rate-limit monitoring and sleep-until-reset
    - Exponential backoff on 403/429/5xx errors
    """

    def __init__(self, token: str | None = None):
        self.token = token or config.github.token
        self.base_url = config.github.api_base_url
        self.per_page = config.github.per_page
        self.session = requests.Session()

        # Set default headers
        self.session.headers.update({
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitHub-Analytics-Pipeline/1.0",
        })

        if self.token:
            self.session.headers["Authorization"] = f"Bearer {self.token}"
            logger.info("GitHub client initialized with authentication (5,000 req/hr)")
        else:
            logger.warning(
                "GitHub client initialized WITHOUT authentication (60 req/hr). "
                "Set GITHUB_TOKEN in .env for higher rate limits."
            )

        # Rate limit tracking
        self.rate_limit_remaining: int = 5000
        self.rate_limit_reset: float = 0

    # ------------------------------------------------------------------
    # Core HTTP
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        url: str,
        params: dict | None = None,
        max_retries: int = 5,
    ) -> requests.Response:
        """
        Make an HTTP request with rate-limit handling and exponential backoff.
        """
        if not url.startswith("http"):
            url = f"{self.base_url}{url}"

        for attempt in range(max_retries):
            # Check if we need to wait for rate limit reset
            if self.rate_limit_remaining <= 1:
                self._wait_for_rate_limit_reset()

            try:
                response = self.session.request(method, url, params=params, timeout=30)

                # Update rate limit tracking from response headers
                self._update_rate_limit(response)

                if response.status_code == 200:
                    return response

                if response.status_code == 204:
                    return response  # No content (valid for some endpoints)

                if response.status_code in (403, 429):
                    # Rate limited — wait and retry
                    retry_after = self._get_retry_after(response)
                    logger.warning(
                        f"Rate limited (HTTP {response.status_code}). "
                        f"Waiting {retry_after:.0f}s before retry {attempt + 1}/{max_retries}"
                    )
                    time.sleep(retry_after)
                    continue

                if response.status_code >= 500:
                    # Server error — exponential backoff
                    wait = min(2 ** attempt * 1, 60)
                    logger.warning(
                        f"Server error (HTTP {response.status_code}). "
                        f"Retrying in {wait}s ({attempt + 1}/{max_retries})"
                    )
                    time.sleep(wait)
                    continue

                if response.status_code == 404:
                    logger.warning(f"Resource not found: {url}")
                    return response

                # Other client errors — don't retry
                response.raise_for_status()

            except requests.exceptions.ConnectionError as e:
                wait = min(2 ** attempt * 2, 60)
                logger.warning(f"Connection error: {e}. Retrying in {wait}s")
                time.sleep(wait)

            except requests.exceptions.Timeout:
                wait = min(2 ** attempt * 2, 60)
                logger.warning(f"Request timeout. Retrying in {wait}s")
                time.sleep(wait)

        raise GitHubClientError(
            f"Failed after {max_retries} retries: {method} {url}"
        )

    def _update_rate_limit(self, response: requests.Response) -> None:
        """Update rate limit tracking from response headers."""
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset = response.headers.get("X-RateLimit-Reset")

        if remaining is not None:
            self.rate_limit_remaining = int(remaining)
        if reset is not None:
            self.rate_limit_reset = float(reset)

        if self.rate_limit_remaining <= 100:
            logger.info(
                f"Rate limit low: {self.rate_limit_remaining} requests remaining"
            )

    def _wait_for_rate_limit_reset(self) -> None:
        """Sleep until the rate limit resets."""
        now = time.time()
        wait = max(self.rate_limit_reset - now + 5, 10)  # +5s buffer
        logger.warning(
            f"Rate limit exhausted. Sleeping {wait:.0f}s until reset..."
        )
        time.sleep(wait)
        self.rate_limit_remaining = 5000  # Reset counter

    def _get_retry_after(self, response: requests.Response) -> float:
        """Get retry-after time from response."""
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            return float(retry_after)
        # Fall back to rate limit reset time
        now = time.time()
        return max(self.rate_limit_reset - now + 5, 30)

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    def _paginate(
        self,
        url: str,
        params: dict | None = None,
        max_pages: int = 100,
    ) -> Generator[list[dict], None, None]:
        """
        Auto-paginate through GitHub API results.
        Yields one page of results at a time.
        """
        params = params or {}
        params.setdefault("per_page", self.per_page)
        page = 1

        while page <= max_pages:
            params["page"] = page
            response = self._request("GET", url, params=params)

            if response.status_code == 404:
                return

            data = response.json()

            if not data:
                return  # No more results

            yield data

            # Check for next page via Link header
            link_header = response.headers.get("Link", "")
            if 'rel="next"' not in link_header:
                return

            page += 1

    def get_all_pages(
        self,
        url: str,
        params: dict | None = None,
        max_pages: int = 100,
    ) -> list[dict]:
        """Fetch all pages and return as a flat list."""
        results = []
        for page_data in self._paginate(url, params, max_pages):
            if isinstance(page_data, list):
                results.extend(page_data)
            else:
                results.append(page_data)
        return results

    # ------------------------------------------------------------------
    # GitHub API Methods
    # ------------------------------------------------------------------

    def get_authenticated_user(self) -> dict:
        """Get the authenticated user's profile."""
        response = self._request("GET", "/user")
        return response.json()

    def get_user_repos(
        self,
        username: str | None = None,
        repo_type: str = "owner",
        sort: str = "updated",
        max_repos: int = 50,
    ) -> list[dict]:
        """
        Fetch repositories for a user.

        Args:
            username: GitHub username. If None, fetches authenticated user's repos.
            repo_type: Type filter — 'all', 'owner', 'member'.
            sort: Sort by — 'created', 'updated', 'pushed', 'full_name'.
            max_repos: Maximum number of repos to return.
        """
        if username:
            url = f"/users/{username}/repos"
            params = {"type": repo_type, "sort": sort}
        else:
            url = "/user/repos"
            params = {"type": repo_type, "sort": sort, "affiliation": "owner"}

        max_pages = (max_repos // self.per_page) + 1
        repos = self.get_all_pages(url, params=params, max_pages=max_pages)
        return repos[:max_repos]

    def get_repo_details(self, owner: str, repo: str) -> dict:
        """Get detailed information about a single repository."""
        response = self._request("GET", f"/repos/{owner}/{repo}")
        return response.json()

    def get_repo_commits(
        self,
        owner: str,
        repo: str,
        since: str | None = None,
        max_pages: int = 10,
    ) -> list[dict]:
        """
        Fetch commits for a repository.

        Args:
            since: ISO 8601 date string (e.g., '2024-01-01T00:00:00Z').
            max_pages: Max pages to fetch (100 commits/page).
        """
        params = {}
        if since:
            params["since"] = since

        return self.get_all_pages(
            f"/repos/{owner}/{repo}/commits",
            params=params,
            max_pages=max_pages,
        )

    def get_repo_pull_requests(
        self,
        owner: str,
        repo: str,
        state: str = "all",
        max_pages: int = 10,
    ) -> list[dict]:
        """Fetch pull requests for a repository."""
        return self.get_all_pages(
            f"/repos/{owner}/{repo}/pulls",
            params={"state": state, "sort": "updated", "direction": "desc"},
            max_pages=max_pages,
        )

    def get_repo_issues(
        self,
        owner: str,
        repo: str,
        state: str = "all",
        max_pages: int = 10,
    ) -> list[dict]:
        """
        Fetch issues for a repository.
        Note: GitHub's issues API also returns PRs; we filter them out.
        """
        all_items = self.get_all_pages(
            f"/repos/{owner}/{repo}/issues",
            params={"state": state, "sort": "updated", "direction": "desc"},
            max_pages=max_pages,
        )
        # Filter out pull requests (they have a 'pull_request' key)
        return [item for item in all_items if "pull_request" not in item]

    def get_repo_contributors(
        self,
        owner: str,
        repo: str,
        max_pages: int = 5,
    ) -> list[dict]:
        """Fetch contributors for a repository."""
        return self.get_all_pages(
            f"/repos/{owner}/{repo}/contributors",
            max_pages=max_pages,
        )

    def get_repo_languages(self, owner: str, repo: str) -> dict:
        """
        Fetch language breakdown for a repository.
        Returns: {language: bytes} mapping.
        """
        response = self._request("GET", f"/repos/{owner}/{repo}/languages")
        if response.status_code == 404:
            return {}
        return response.json()

    def get_rate_limit(self) -> dict:
        """Check current rate limit status."""
        response = self._request("GET", "/rate_limit")
        return response.json()

    def check_connection(self) -> bool:
        """Verify the client can connect and authenticate."""
        try:
            rate_limit = self.get_rate_limit()
            core = rate_limit.get("resources", {}).get("core", {})
            logger.info(
                f"GitHub API connected. "
                f"Rate limit: {core.get('remaining')}/{core.get('limit')} "
                f"(resets at {core.get('reset')})"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to connect to GitHub API: {e}")
            return False
