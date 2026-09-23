interface Props {
  label: string;
  className?: string;
}

export function StatusBadge({ label, className = '' }: Props) {
  return (
    <span className={`sg-badge ${className}`}>
      {label}
    </span>
  );
}
