"use client";

import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
import type { LanguageUsage } from "@/types";
import styles from "./LanguageDonut.module.css";

const COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
  "var(--chart-6)",
  "var(--chart-7)",
  "var(--chart-8)",
];

interface Props {
  data: LanguageUsage[];
}

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload as LanguageUsage;
  return (
    <div className={styles.tooltip}>
      <p className={styles.tooltipName}>{d.language}</p>
      <p className={styles.tooltipPct}>{d.percentage}%</p>
      <p className={styles.tooltipSub}>{d.repo_count} repo{d.repo_count !== 1 ? "s" : ""}</p>
    </div>
  );
}

export default function LanguageDonut({ data }: Props) {
  if (!data.length) {
    return (
      <div className={`card ${styles.wrap}`}>
        <p className="section-title">Language Distribution</p>
        <div className={styles.empty}>No language data available</div>
      </div>
    );
  }

  const top = data.slice(0, 8);

  return (
    <div className={`card ${styles.wrap} fade-in-up`}>
      <p className="section-title">Language Distribution</p>
      <ResponsiveContainer width="100%" height={200}>
        <PieChart>
          <Pie
            data={top}
            cx="50%"
            cy="50%"
            innerRadius={55}
            outerRadius={80}
            paddingAngle={3}
            dataKey="percentage"
            nameKey="language"
          >
            {top.map((entry, index) => (
              <Cell
                key={entry.language}
                fill={COLORS[index % COLORS.length]}
                stroke="var(--bg-surface)"
                strokeWidth={2}
              />
            ))}
          </Pie>
          <Tooltip content={<CustomTooltip />} />
        </PieChart>
      </ResponsiveContainer>
      {/* Legend */}
      <div className={styles.legend}>
        {top.slice(0, 6).map((lang, i) => (
          <div key={lang.language} className={styles.legendItem}>
            <span
              className={styles.legendDot}
              style={{ background: COLORS[i % COLORS.length] }}
            />
            <span className={styles.legendName}>{lang.language}</span>
            <span className={styles.legendPct}>{lang.percentage}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
