"use client";

import { useEffect, useState, useCallback } from "react";
import { getRepositories, getUniqueLanguages } from "@/lib/api";
import type { RepositoryOverview } from "@/types";
import ErrorState from "@/components/ui/ErrorState";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import styles from "./page.module.css";

type SortBy = "stars_count" | "forks_count" | "total_commits" | "name";

const LANGUAGE_COLORS: Record<string, string> = {
  TypeScript: "#3178c6",
  JavaScript: "#f7df1e",
  Python: "#3776ab",
  Go: "#00add8",
  Rust: "#dea584",
  Java: "#b07219",
  "C++": "#f34b7d",
  C: "#555555",
  Ruby: "#701516",
  Swift: "#fa7343",
  Kotlin: "#a97bff",
  Dart: "#00b4ab",
  PHP: "#4f5d95",
  "C#": "#178600",
  Shell: "#89e051",
  HTML: "#e34c26",
  CSS: "#563d7c",
  Vue: "#41b883",
};

function getLangColor(lang: string | null): string {
  if (!lang) return "var(--text-tertiary)";
  return LANGUAGE_COLORS[lang] ?? "var(--accent-violet)";
}

export default function RepositoriesPage() {
  const [repos, setRepos] = useState<RepositoryOverview[]>([]);
  const [total, setTotal] = useState(0);
  const [languages, setLanguages] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [sortBy, setSortBy] = useState<SortBy>("stars_count");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [language, setLanguage] = useState<string>("");
  const [offset, setOffset] = useState(0);
  const PAGE_SIZE = 20;

  const fetchRepos = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getRepositories({ sortBy, order, limit: PAGE_SIZE, offset, language: language || undefined });
      setRepos(data.repositories);
      setTotal(data.total_count);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [sortBy, order, language, offset]);

  useEffect(() => {
    getUniqueLanguages()
      .then(setLanguages)
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchRepos();
  }, [fetchRepos]);

  // Reset offset when filters change
  useEffect(() => {
    setOffset(0);
  }, [sortBy, order, language]);

  if (error) {
    return <ErrorState title="Could not load repositories" message={error} retry={fetchRepos} />;
  }

  return (
    <div className={styles.page}>
      {/* Filters bar */}
      <div className={styles.filters} id="repo-filters">
        <div className={styles.filterGroup}>
          <label className={styles.filterLabel}>Sort by</label>
          <select
            id="sort-select"
            className={styles.select}
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortBy)}
          >
            <option value="stars_count">Stars</option>
            <option value="forks_count">Forks</option>
            <option value="total_commits">Commits</option>
            <option value="name">Name</option>
          </select>
        </div>
        <div className={styles.filterGroup}>
          <label className={styles.filterLabel}>Order</label>
          <select
            id="order-select"
            className={styles.select}
            value={order}
            onChange={(e) => setOrder(e.target.value as "asc" | "desc")}
          >
            <option value="desc">Descending</option>
            <option value="asc">Ascending</option>
          </select>
        </div>
        {languages.length > 0 && (
          <div className={styles.filterGroup}>
            <label className={styles.filterLabel}>Language</label>
            <select
              id="language-select"
              className={styles.select}
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
            >
              <option value="">All languages</option>
              {languages.map((l) => (
                <option key={l} value={l}>{l}</option>
              ))}
            </select>
          </div>
        )}
        <span className={styles.totalBadge}>{total.toLocaleString()} repositories</span>
      </div>

      {/* Table */}
      {loading ? (
        <LoadingSpinner message="Loading repositories..." />
      ) : repos.length === 0 ? (
        <div className={styles.empty}>No repositories found.</div>
      ) : (
        <>
          <div className={styles.tableWrap}>
            <table className={styles.table} id="repos-table">
              <thead>
                <tr>
                  <th>Repository</th>
                  <th>Language</th>
                  <th>Stars</th>
                  <th>Forks</th>
                  <th>Commits</th>
                  <th>PRs</th>
                  <th>Issues</th>
                </tr>
              </thead>
              <tbody>
                {repos.map((repo) => (
                  <tr key={repo.repository_id} className={styles.row}>
                    <td>
                      <div className={styles.repoName}>
                        {repo.html_url ? (
                          <a href={repo.html_url} target="_blank" rel="noreferrer" className={styles.repoLink}>
                            {repo.full_name}
                          </a>
                        ) : (
                          <span>{repo.full_name}</span>
                        )}
                        {repo.description && (
                          <p className={styles.repoDesc}>{repo.description}</p>
                        )}
                      </div>
                    </td>
                    <td>
                      {repo.language ? (
                        <span className={styles.langBadge} style={{ "--lang-color": getLangColor(repo.language) } as React.CSSProperties}>
                          <span className={styles.langDot} style={{ background: getLangColor(repo.language) }} />
                          {repo.language}
                        </span>
                      ) : (
                        <span className={styles.na}>—</span>
                      )}
                    </td>
                    <td><span className={styles.num}>⭐ {repo.stars_count.toLocaleString()}</span></td>
                    <td><span className={styles.num}>{repo.forks_count.toLocaleString()}</span></td>
                    <td><span className={styles.num}>{repo.total_commits.toLocaleString()}</span></td>
                    <td><span className={styles.num}>{repo.total_prs.toLocaleString()}</span></td>
                    <td><span className={styles.num}>{repo.total_issues.toLocaleString()}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {total > PAGE_SIZE && (
            <div className={styles.pagination} id="pagination">
              <button
                id="prev-btn"
                className={styles.pageBtn}
                disabled={offset === 0}
                onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
              >
                ← Prev
              </button>
              <span className={styles.pageInfo}>
                {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
              </span>
              <button
                id="next-btn"
                className={styles.pageBtn}
                disabled={offset + PAGE_SIZE >= total}
                onClick={() => setOffset((o) => o + PAGE_SIZE)}
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
