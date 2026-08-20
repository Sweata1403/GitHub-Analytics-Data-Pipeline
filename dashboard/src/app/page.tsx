import { getDashboardSummary } from "@/lib/api";
import ErrorState from "@/components/ui/ErrorState";
import StatCard from "@/components/cards/StatCard";
import CommitTimeline from "@/components/charts/CommitTimeline";
import LanguageDonut from "@/components/charts/LanguageDonut";
import PRStatusPanel from "@/components/charts/PRStatusPanel";
import ContributorList from "@/components/charts/ContributorList";
import CommitHeatmap from "@/components/charts/CommitHeatmap";
import type { DashboardSummary } from "@/types";

// Icons
function RepoIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 3h18v18H3zM9 3v18M3 9h18" />
    </svg>
  );
}
function CommitIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="4" /><line x1="1.05" y1="12" x2="7" y2="12" /><line x1="17.01" y1="12" x2="22.96" y2="12" />
    </svg>
  );
}
function PRIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="18" cy="18" r="3" /><circle cx="6" cy="6" r="3" /><path d="M13 6h3a2 2 0 0 1 2 2v7" /><line x1="6" y1="9" x2="6" y2="21" />
    </svg>
  );
}
function IssueIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  );
}
function ContribIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  );
}
function StarIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  );
}
function ForkIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="18" r="3" /><circle cx="6" cy="6" r="3" /><circle cx="18" cy="6" r="3" /><path d="M18 9v1a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V9" /><line x1="12" y1="12" x2="12" y2="15" />
    </svg>
  );
}

// Fetch heatmap data separately to avoid blocking the whole page
async function getHeatmapData() {
  try {
    const { getCommitHeatmap } = await import("@/lib/api");
    return await getCommitHeatmap();
  } catch {
    return [];
  }
}

export default async function OverviewPage() {
  let summary: DashboardSummary | null = null;
  let error: string | null = null;

  try {
    summary = await getDashboardSummary();
  } catch (e) {
    error = e instanceof Error ? e.message : "Unknown error";
  }

  const heatmapData = await getHeatmapData();

  if (error || !summary) {
    return <ErrorState title="Could not load dashboard" message={error ?? "Unknown error. Is the FastAPI backend running on port 8000?"} />;
  }

  return (
    <>
      {/* KPI Stats */}
      <div className="stats-grid">
        <StatCard id="stat-repos" label="Repositories" value={summary.total_repositories} icon={<RepoIcon />} accent="violet" sub={summary.top_language ? `Top: ${summary.top_language}` : undefined} />
        <StatCard id="stat-commits" label="Total Commits" value={summary.total_commits} icon={<CommitIcon />} accent="green" sub={`${summary.recent_commits_30d.toLocaleString()} in 30d`} />
        <StatCard id="stat-prs" label="Pull Requests" value={summary.total_pull_requests} icon={<PRIcon />} accent="blue" sub={summary.pr_stats.merge_rate_pct != null ? `${summary.pr_stats.merge_rate_pct}% merge rate` : undefined} />
        <StatCard id="stat-issues" label="Issues" value={summary.total_issues} icon={<IssueIcon />} accent="amber" sub={`${summary.open_issues} open`} />
        <StatCard id="stat-contributors" label="Contributors" value={summary.total_contributors} icon={<ContribIcon />} accent="cyan" />
        <StatCard id="stat-stars" label="Stars" value={summary.total_stars} icon={<StarIcon />} accent="amber" />
        <StatCard id="stat-forks" label="Forks" value={summary.total_forks} icon={<ForkIcon />} accent="rose" />
        {summary.avg_merge_time_hours != null && (
          <StatCard id="stat-merge-time" label="Avg Merge Time" value={`${Math.round(summary.avg_merge_time_hours)}h`} icon={<PRIcon />} accent="violet" sub="across all PRs" />
        )}
      </div>

      {/* Commit Timeline + Language Donut */}
      <div className="charts-grid">
        <CommitTimeline data={summary.commit_timeline} totalCommits={summary.total_commits} />
        <LanguageDonut data={summary.language_distribution} />
      </div>

      {/* PR + Issue Panels */}
      <PRStatusPanel prStats={summary.pr_stats} issueStats={summary.issue_stats} />

      <div className="charts-row" style={{ marginTop: "1rem" }}>
        {/* Top Contributors */}
        <ContributorList contributors={summary.top_contributors} />
        {/* Commit Heatmap */}
        <CommitHeatmap data={heatmapData} />
      </div>
    </>
  );
}
