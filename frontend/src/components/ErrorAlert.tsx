import { AlertTriangle, X, RotateCcw } from 'lucide-react';
import { useState } from 'react';

interface Props {
  message: string;
  onRetry?: () => void;
}

export function ErrorAlert({ message, onRetry }: Props) {
  const [visible, setVisible] = useState(true);
  if (!visible) return null;

  return (
    <div
      className="sg-panel p-4 flex items-start gap-3"
      style={{ borderColor: 'rgba(239, 68, 68, 0.25)' }}
    >
      <AlertTriangle className="h-4 w-4 text-[#ef4444] flex-shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <p className="font-semibold text-sm text-[#ef4444]">Analysis could not be completed</p>
        <p className="text-sm text-[#8b8d98] mt-1 break-words">{message}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="sg-btn sg-btn-secondary mt-3 text-xs"
          >
            <RotateCcw className="h-3 w-3" />
            Try Again
          </button>
        )}
      </div>
      <button
        onClick={() => setVisible(false)}
        className="p-1 rounded text-[#5c5e6a] hover:text-[#8b8d98] transition-colors flex-shrink-0"
        aria-label="Dismiss error"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
