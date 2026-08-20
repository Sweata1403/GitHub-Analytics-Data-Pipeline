import styles from "./LoadingSpinner.module.css";

export default function LoadingSpinner({ message = "Loading..." }: { message?: string }) {
  return (
    <div className={styles.wrap}>
      <div className={styles.spinner} />
      <p className={styles.message}>{message}</p>
    </div>
  );
}

export function CardSkeleton({ height = 220 }: { height?: number }) {
  return (
    <div
      className={`card skeleton`}
      style={{ height, minHeight: height }}
      aria-label="Loading..."
    />
  );
}
