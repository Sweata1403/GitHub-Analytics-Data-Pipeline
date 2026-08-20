import styles from "./ErrorState.module.css";

interface Props {
  title?: string;
  message?: string;
  retry?: () => void;
}

export default function ErrorState({
  title = "Something went wrong",
  message = "Could not load data from the API. Make sure the backend is running on port 8000.",
  retry,
}: Props) {
  return (
    <div className={styles.wrap}>
      <div className={styles.icon}>
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </div>
      <h2 className={styles.title}>{title}</h2>
      <p className={styles.message}>{message}</p>
      {retry && (
        <button className={styles.retryBtn} onClick={retry} id="retry-btn">
          Try Again
        </button>
      )}
    </div>
  );
}
