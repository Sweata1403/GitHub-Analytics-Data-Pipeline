import type { PRStats, IssueStats } from "@/types";
import styles from "./PRStatusPanel.module.css";

interface Props {
  prStats: PRStats;
  issueStats: IssueStats;
}

function StatRow({
  label,
  value,
  color,
  bar,
}: {
  label: string;
  value: string | number;
  color: string;
  bar?: number; // 0-100
}) {
  return (
    <div className={styles.statRow}>
      <div className={styles.statRowHead}>
        <span className={styles.statDot} style={{ background: color }} />
        <span className={styles.statLabel}>{label}</span>
        <span className={styles.statValue}>{typeof value === "number" ? value.toLocaleString() : value}</span>
      </div>
      {bar !== undefined && (
        <div className={styles.barTrack}>
          <div
            className={styles.barFill}
            style={{ width: `${Math.min(bar, 100)}%`, background: color }}
          />
        </div>
      )}
    </div>
  );
}

export default function PRStatusPanel({ prStats, issueStats }: Props) {
  const mergeRate = prStats.merge_rate_pct ?? 0;
  const closeRate =
    issueStats.total_issues > 0
      ? Math.round((issueStats.closed_issues / issueStats.total_issues) * 100)
      : 0;

  return (
    <div className={styles.grid}>
      {/* PR Panel */}
      <div className={`card ${styles.panel} fade-in-up`}>
        <p className="section-title">Pull Requests</p>
        <div className={styles.bigStat}>
          <span className={styles.bigNumber}>{prStats.total_prs.toLocaleString()}</span>
          <span className={styles.bigLabel}>total PRs</span>
        </div>
        <div className={styles.rows}>
          <StatRow label="Open" value={prStats.open_prs} color="var(--accent-blue)" bar={(prStats.open_prs / Math.max(prStats.total_prs, 1)) * 100} />
          <StatRow label="Merged" value={prStats.merged_prs} color="var(--accent-violet)" bar={(prStats.merged_prs / Math.max(prStats.total_prs, 1)) * 100} />
          <StatRow label="Closed (unmerged)" value={prStats.closed_unmerged} color="var(--accent-rose)" bar={(prStats.closed_unmerged / Math.max(prStats.total_prs, 1)) * 100} />
        </div>
        <div className={styles.metrics}>
          <div className={styles.metric}>
            <span className={styles.metricVal}>{mergeRate}%</span>
            <span className={styles.metricLabel}>Merge rate</span>
          </div>
          <div className={styles.metric}>
            <span className={styles.metricVal}>
              {prStats.avg_merge_time_hours != null
                ? `${Math.round(prStats.avg_merge_time_hours)}h`
                : "—"}
            </span>
            <span className={styles.metricLabel}>Avg merge time</span>
          </div>
          <div className={styles.metric}>
            <span className={styles.metricVal}>
              {prStats.median_merge_time_hours != null
                ? `${Math.round(prStats.median_merge_time_hours)}h`
                : "—"}
            </span>
            <span className={styles.metricLabel}>Median merge</span>
          </div>
        </div>
      </div>

      {/* Issue Panel */}
      <div className={`card ${styles.panel} fade-in-up`}>
        <p className="section-title">Issues</p>
        <div className={styles.bigStat}>
          <span className={styles.bigNumber}>{issueStats.total_issues.toLocaleString()}</span>
          <span className={styles.bigLabel}>total issues</span>
        </div>
        <div className={styles.rows}>
          <StatRow label="Open" value={issueStats.open_issues} color="var(--accent-amber)" bar={(issueStats.open_issues / Math.max(issueStats.total_issues, 1)) * 100} />
          <StatRow label="Closed" value={issueStats.closed_issues} color="var(--accent-green)" bar={(issueStats.closed_issues / Math.max(issueStats.total_issues, 1)) * 100} />
        </div>
        <div className={styles.metrics}>
          <div className={styles.metric}>
            <span className={styles.metricVal}>{closeRate}%</span>
            <span className={styles.metricLabel}>Close rate</span>
          </div>
          <div className={styles.metric}>
            <span className={styles.metricVal}>
              {issueStats.avg_close_time_hours != null
                ? `${Math.round(issueStats.avg_close_time_hours)}h`
                : "—"}
            </span>
            <span className={styles.metricLabel}>Avg close time</span>
          </div>
          <div className={styles.metric}>
            <span className={styles.metricVal}>
              {issueStats.median_close_time_hours != null
                ? `${Math.round(issueStats.median_close_time_hours)}h`
                : "—"}
            </span>
            <span className={styles.metricLabel}>Median close</span>
          </div>
        </div>
      </div>
    </div>
  );
}
