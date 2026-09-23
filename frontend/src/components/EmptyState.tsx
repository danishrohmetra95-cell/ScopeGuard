import { type ReactNode } from 'react';
import { FileSearch } from 'lucide-react';

export function EmptyState({
  title,
  description,
  icon,
  action,
}: {
  title: string;
  description?: string;
  icon?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="p-3 rounded-lg mb-4" style={{ background: 'var(--color-sg-elevated)' }}>
        <div className="text-[#5c5e6a]">
          {icon || <FileSearch className="h-8 w-8" />}
        </div>
      </div>
      <h3 className="text-sm font-semibold text-[#8b8d98]">{title}</h3>
      {description && (
        <p className="text-sm text-[#5c5e6a] mt-1.5 max-w-sm leading-relaxed">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
