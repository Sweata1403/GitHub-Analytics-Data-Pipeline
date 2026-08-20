import type { TopContributor } from "@/types";
import styles from "./ContributorList.module.css";

interface Props {
  contributors: TopContributor[];
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleDateString("en-US", { month: "short", year: "numeric" });
}

export default function ContributorList({ contributors }: Props) {
  if (!contributors.length) {
    return (
      <div className={`card ${styles.wrap}`}>
        <p className="section-title">Top Contributors</p>
        <div className={styles.empty}>No contributor data available</div>
      </div>
    );
  }

  const maxCommits = contributors[0]?.total_commits ?? 1;

  return (
    <div className={`card ${styles.wrap} fade-in-up`}>
      <p className="section-title">Top Contributors</p>
      <div className={styles.list}>
        {contributors.map((c, i) => (
          <div key={c.login} className={styles.item}>
            <span className={styles.rank}>#{i + 1}</span>
            {c.avatar_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={c.avatar_url}
                alt={c.login}
                className={styles.avatar}
                width={32}
                height={32}
              />
            ) : (
              <div className={styles.avatarFallback}>
                {c.login[0]?.toUpperCase()}
              </div>
            )}
            <div className={styles.info}>
              <div className={styles.infoRow}>
                <span className={styles.login}>{c.login}</span>
                <span className={styles.commits}>{c.total_commits.toLocaleString()} commits</span>
              </div>
              <div className={styles.barTrack}>
                <div
                  className={styles.barFill}
                  style={{ width: `${(c.total_commits / maxCommits) * 100}%` }}
                />
              </div>
              <div className={styles.meta}>
                <span>
                  <span className={styles.add}>+{c.total_additions.toLocaleString()}</span>
                  <span className={styles.del}> −{c.total_deletions.toLocaleString()}</span>
                </span>
                <span className={styles.repos}>{c.repos_contributed_to} repo{c.repos_contributed_to !== 1 ? "s" : ""}</span>
                <span className={styles.since}>since {formatDate(c.first_commit)}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
