"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { CommitTimelinePoint } from "@/types";
import styles from "./CommitTimeline.module.css";

interface Props {
  data: CommitTimelinePoint[];
  totalCommits: number;
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload as CommitTimelinePoint;
  return (
    <div className={styles.tooltip}>
      <p className={styles.tooltipDate}>{formatDate(label)}</p>
      <div className={styles.tooltipRow}>
        <span className={styles.tooltipDot} style={{ background: "var(--accent-violet)" }} />
        <span>{d.commit_count} commits</span>
      </div>
      <div className={styles.tooltipRow}>
        <span className={styles.tooltipDot} style={{ background: "var(--accent-green)" }} />
        <span>{d.unique_authors} authors</span>
      </div>
      <div className={styles.tooltipRow}>
        <span style={{ color: "var(--accent-green)", fontSize: "0.72rem" }}>+{d.additions.toLocaleString()}</span>
        <span style={{ color: "var(--accent-rose)", fontSize: "0.72rem", marginLeft: "0.5rem" }}>-{d.deletions.toLocaleString()}</span>
      </div>
    </div>
  );
}

export default function CommitTimeline({ data, totalCommits }: Props) {
  if (!data.length) {
    return (
      <div className={`card ${styles.wrap}`}>
        <div className={styles.head}>
          <p className="section-title">Commit Activity</p>
          <span className={styles.total}>0 total</span>
        </div>
        <div className={styles.empty}>No commit data available</div>
      </div>
    );
  }

  return (
    <div className={`card ${styles.wrap} fade-in-up`}>
      <div className={styles.head}>
        <p className="section-title">Commit Activity — Last 30 Days</p>
        <span className={styles.total}>{totalCommits.toLocaleString()} total</span>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="commitGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="var(--accent-violet)" stopOpacity={0.35} />
              <stop offset="95%" stopColor="var(--accent-violet)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={formatDate}
            tick={{ fill: "var(--text-secondary)", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fill: "var(--text-secondary)", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip content={<CustomTooltip />} />
          <Area
            type="monotone"
            dataKey="commit_count"
            stroke="var(--accent-violet)"
            strokeWidth={2}
            fill="url(#commitGrad)"
            dot={false}
            activeDot={{ r: 4, fill: "var(--accent-violet)", strokeWidth: 0 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
