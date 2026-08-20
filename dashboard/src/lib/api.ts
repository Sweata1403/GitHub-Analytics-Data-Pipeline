/**
 * Typed API client for the GitHub Analytics FastAPI backend.
 * Base URL is read from NEXT_PUBLIC_API_URL (default: http://localhost:8000/api/v1)
 */

import type {
  DashboardSummary,
  CommitTimeline,
  TopContributor,
  RepositoryList,
  HeatmapCell,
  HealthCheck,
} from "@/types";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    next: { revalidate: 60 }, // ISR — revalidate every 60s
  });
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText} — ${path}`);
  }
  return res.json() as Promise<T>;
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

export async function getDashboardSummary(): Promise<DashboardSummary> {
  return apiFetch<DashboardSummary>("/dashboard/summary");
}

// ─── Commits ──────────────────────────────────────────────────────────────────

export async function getCommitTimeline(
  period: "daily" | "weekly" | "monthly" = "daily",
  limit = 90,
  repositoryId?: number
): Promise<CommitTimeline> {
  const params = new URLSearchParams({ period, limit: String(limit) });
  if (repositoryId != null) params.set("repository_id", String(repositoryId));
  return apiFetch<CommitTimeline>(`/commits/timeline?${params}`);
}

export async function getTopContributors(
  limit = 20,
  repositoryId?: number
): Promise<TopContributor[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (repositoryId != null) params.set("repository_id", String(repositoryId));
  return apiFetch<TopContributor[]>(`/commits/top-contributors?${params}`);
}

export async function getCommitHeatmap(
  repositoryId?: number,
  year?: number
): Promise<HeatmapCell[]> {
  const params = new URLSearchParams();
  if (repositoryId != null) params.set("repository_id", String(repositoryId));
  if (year != null) params.set("year", String(year));
  return apiFetch<HeatmapCell[]>(`/commits/heatmap?${params}`);
}

// ─── Repositories ─────────────────────────────────────────────────────────────

export async function getRepositories(opts?: {
  sortBy?: "stars_count" | "forks_count" | "total_commits" | "name";
  order?: "asc" | "desc";
  limit?: number;
  offset?: number;
  language?: string;
}): Promise<RepositoryList> {
  const params = new URLSearchParams();
  if (opts?.sortBy) params.set("sort_by", opts.sortBy);
  if (opts?.order) params.set("order", opts.order);
  if (opts?.limit != null) params.set("limit", String(opts.limit));
  if (opts?.offset != null) params.set("offset", String(opts.offset));
  if (opts?.language) params.set("language", opts.language);
  return apiFetch<RepositoryList>(`/repositories?${params}`);
}

export async function getUniqueLanguages(): Promise<string[]> {
  return apiFetch<string[]>("/repositories/languages/unique");
}

// ─── Health ───────────────────────────────────────────────────────────────────

export async function getHealth(): Promise<HealthCheck> {
  return apiFetch<HealthCheck>("/health");
}
