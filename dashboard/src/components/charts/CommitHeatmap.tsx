import type { HeatmapCell } from "@/types";
import styles from "./CommitHeatmap.module.css";

interface Props {
  data: HeatmapCell[];
}

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const HOURS = Array.from({ length: 24 }, (_, i) =>
  i === 0 ? "12am" : i < 12 ? `${i}am` : i === 12 ? "12pm" : `${i - 12}pm`
);

function getColor(count: number, max: number): string {
  if (count === 0 || max === 0) return "var(--bg-elevated)";
  const ratio = count / max;
  if (ratio < 0.15) return "rgba(124,58,237,0.15)";
  if (ratio < 0.35) return "rgba(124,58,237,0.35)";
  if (ratio < 0.60) return "rgba(124,58,237,0.6)";
  if (ratio < 0.80) return "rgba(124,58,237,0.8)";
  return "var(--accent-violet)";
}

export default function CommitHeatmap({ data }: Props) {
  // Build lookup: [day][hour] = count
  const grid: number[][] = Array.from({ length: 7 }, () => new Array(24).fill(0));
  let maxCount = 0;

  for (const cell of data) {
    const dow = cell.day_of_week; // 0=Sun
    const hr = cell.hour;
    if (dow >= 0 && dow < 7 && hr >= 0 && hr < 24) {
      grid[dow][hr] = cell.commit_count;
      if (cell.commit_count > maxCount) maxCount = cell.commit_count;
    }
  }

  if (maxCount === 0) {
    return (
      <div className={`card ${styles.wrap}`}>
        <p className="section-title">Commit Heatmap — Day × Hour</p>
        <div className={styles.empty}>No heatmap data available</div>
      </div>
    );
  }

  return (
    <div className={`card ${styles.wrap} fade-in-up`}>
      <div className={styles.head}>
        <p className="section-title">Commit Heatmap — Day × Hour</p>
        <div className={styles.legend}>
          <span className={styles.legendLabel}>Less</span>
          {[0, 0.2, 0.4, 0.65, 0.9].map((r, i) => (
            <div
              key={i}
              className={styles.legendCell}
              style={{ background: getColor(r * maxCount, maxCount) }}
            />
          ))}
          <span className={styles.legendLabel}>More</span>
        </div>
      </div>
      <div className={styles.heatmapOuter}>
        {/* Hour labels */}
        <div className={styles.hourRow}>
          <div className={styles.dayLabelPlaceholder} />
          {HOURS.map((h, hi) => (
            <div key={hi} className={styles.hourLabel}>
              {hi % 3 === 0 ? h : ""}
            </div>
          ))}
        </div>
        {/* Rows */}
        {DAYS.map((day, di) => (
          <div key={day} className={styles.row}>
            <span className={styles.dayLabel}>{day}</span>
            {grid[di].map((count, hi) => (
              <div
                key={hi}
                className={styles.cell}
                style={{ background: getColor(count, maxCount) }}
                title={`${day} ${HOURS[hi]}: ${count} commit${count !== 1 ? "s" : ""}`}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
