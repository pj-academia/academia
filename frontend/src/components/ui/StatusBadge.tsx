import styles from "./StatusBadge.module.css";

export type StatusTone = "ok" | "warning" | "error" | "neutral";

interface StatusBadgeProps {
  tone: StatusTone;
  label: string;
}

export function StatusBadge({ tone, label }: StatusBadgeProps) {
  return (
    <span className={`${styles.badge} ${styles[tone]}`} data-tone={tone}>
      {label}
    </span>
  );
}
