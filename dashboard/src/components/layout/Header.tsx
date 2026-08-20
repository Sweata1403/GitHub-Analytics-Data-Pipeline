"use client";

import { usePathname } from "next/navigation";
import styles from "./Header.module.css";

const PAGE_TITLES: Record<string, { title: string; subtitle: string }> = {
  "/": { title: "Overview", subtitle: "All repositories at a glance" },
  "/repositories": { title: "Repositories", subtitle: "Browse and filter tracked repos" },
};

export default function Header() {
  const pathname = usePathname();
  const page = PAGE_TITLES[pathname] ?? { title: "Dashboard", subtitle: "" };

  const now = new Date();
  const timeStr = now.toLocaleString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <header className={styles.header}>
      <div className={styles.titleGroup}>
        <h1 className={styles.title}>{page.title}</h1>
        {page.subtitle && <p className={styles.subtitle}>{page.subtitle}</p>}
      </div>
      <div className={styles.right}>
        <span className={styles.time}>{timeStr}</span>
        <a
          href="http://localhost:8000/api/v1/docs"
          target="_blank"
          rel="noreferrer"
          className={styles.apiLink}
          id="api-docs-link"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
            <polyline points="15 3 21 3 21 9" />
            <line x1="10" y1="14" x2="21" y2="3" />
          </svg>
          API Docs
        </a>
      </div>
    </header>
  );
}
