// TypeScript types mirroring the FastAPI Pydantic response schemas

export interface RepositoryOverview {
  repository_id: number;
  full_name: string;
  owner: string;
  name: string;
  description: string | null;
  language: string | null;
  stars_count: number;
  forks_count: number;
  is_fork: boolean;
  created_at: string | null;
  html_url: string | null;
  total_commits: number;
  total_prs: number;
  total_issues: number;
  total_additions: number;
  total_deletions: number;
}

export interface RepositoryList {
  repositories: RepositoryOverview[];
  total_count: number;
}

export interface CommitTimelinePoint {
  date: string;
  commit_count: number;
  unique_authors: number;
  additions: number;
  deletions: number;
}

export interface CommitTimeline {
  data: CommitTimelinePoint[];
  total_commits: number;
  period: string;
}

export interface TopContributor {
  login: string;
  avatar_url: string | null;
  total_commits: number;
  repos_contributed_to: number;
  total_additions: number;
  total_deletions: number;
  first_commit: string | null;
  last_commit: string | null;
}

export interface PRStats {
  total_prs: number;
  open_prs: number;
  merged_prs: number;
  closed_unmerged: number;
  avg_merge_time_hours: number | null;
  median_merge_time_hours: number | null;
  merge_rate_pct: number | null;
}

export interface IssueStats {
  total_issues: number;
  open_issues: number;
  closed_issues: number;
  avg_close_time_hours: number | null;
  median_close_time_hours: number | null;
}

export interface LanguageUsage {
  language: string;
  total_bytes: number;
  repo_count: number;
  percentage: number;
}

export interface DashboardSummary {
  total_repositories: number;
  total_commits: number;
  total_pull_requests: number;
  total_issues: number;
  total_contributors: number;
  total_stars: number;
  total_forks: number;
  top_language: string | null;
  avg_merge_time_hours: number | null;
  open_issues: number;
  recent_commits_30d: number;
  commit_timeline: CommitTimelinePoint[];
  top_contributors: TopContributor[];
  language_distribution: LanguageUsage[];
  pr_stats: PRStats;
  issue_stats: IssueStats;
}

export interface HeatmapCell {
  day_of_week: number;
  day_name: string;
  hour: number;
  commit_count: number;
}

export interface HealthCheck {
  status: string;
  database: string;
  version: string;
}
