import styles from "./StatCard.module.css";

interface StatCardProps {
  id?: string;
  label: string;
  value: string | number;
  sub?: string;
  icon: React.ReactNode;
  accent?: "violet" | "green" | "blue" | "amber" | "rose" | "cyan";
  delta?: string;
  deltaDir?: "up" | "down" | "neutral";
}

const ACCENT_MAP: Record<string, string> = {
  violet: "var(--accent-violet)",
  green: "var(--accent-green)",
  blue: "var(--accent-blue)",
  amber: "var(--accent-amber)",
  rose: "var(--accent-rose)",
  cyan: "var(--accent-cyan)",
};

const ACCENT_DIM_MAP: Record<string, string> = {
  violet: "var(--accent-violet-dim)",
  green: "var(--accent-green-dim)",
  blue: "var(--accent-blue-dim)",
  amber: "var(--accent-amber-dim)",
  rose: "var(--accent-rose-dim)",
  cyan: "var(--accent-cyan-dim)",
};

export default function StatCard({
  id,
  label,
  value,
  sub,
  icon,
  accent = "violet",
  delta,
  deltaDir = "neutral",
}: StatCardProps) {
  const color = ACCENT_MAP[accent];
  const dimColor = ACCENT_DIM_MAP[accent];

  return (
    <div
      id={id}
      className={`card ${styles.statCard} fade-in-up`}
      style={{ "--accent-color": color, "--accent-dim": dimColor } as React.CSSProperties}
    >
      <div className={styles.iconWrap}>
        <div className={styles.icon} style={{ background: dimColor, color }}>
          {icon}
        </div>
      </div>
      <div className={styles.body}>
        <p className={styles.label}>{label}</p>
        <p className={styles.value}>{typeof value === "number" ? value.toLocaleString() : value}</p>
        {(sub || delta) && (
          <div className={styles.meta}>
            {sub && <span className={styles.sub}>{sub}</span>}
            {delta && (
              <span
                className={`${styles.delta} ${
                  deltaDir === "up"
                    ? styles.up
                    : deltaDir === "down"
                    ? styles.down
                    : styles.neutral
                }`}
              >
                {delta}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
