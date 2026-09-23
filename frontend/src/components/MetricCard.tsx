interface Props {
  label: string;
  value: string | number;
  mono?: boolean;
}

export function MetricCard({ label, value, mono }: Props) {
  return (
    <div>
      <div className="text-[11px] font-semibold uppercase tracking-wider text-[#5c5e6a] mb-1">
        {label}
      </div>
      <div className={`text-lg font-semibold text-[#e4e4e7] tabular-nums ${mono ? 'font-mono text-base' : ''}`}>
        {value}
      </div>
    </div>
  );
}
