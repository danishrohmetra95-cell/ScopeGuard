/** Shared helpers — ScopeGuard v2 design system */

export function riskColor(level: string): string {
  switch (level) {
    case 'CRITICAL': return 'var(--color-sg-risk-critical)';
    case 'HIGH':     return 'var(--color-sg-risk-high)';
    case 'MEDIUM':   return 'var(--color-sg-risk-medium)';
    case 'LOW':      return 'var(--color-sg-risk-low)';
    default:         return 'var(--color-sg-text-secondary)';
  }
}

export function riskTextClass(level: string): string {
  switch (level) {
    case 'CRITICAL': return 'text-[#ef4444]';
    case 'HIGH':     return 'text-[#f97316]';
    case 'MEDIUM':   return 'text-[#eab308]';
    case 'LOW':      return 'text-[#22c55e]';
    default:         return 'text-[#8b8d98]';
  }
}

export function riskBadgeClasses(level: string): string {
  switch (level) {
    case 'CRITICAL': return 'bg-[rgba(239,68,68,0.1)] text-[#ef4444] border border-[rgba(239,68,68,0.2)]';
    case 'HIGH':     return 'bg-[rgba(249,115,22,0.1)] text-[#f97316] border border-[rgba(249,115,22,0.2)]';
    case 'MEDIUM':   return 'bg-[rgba(234,179,8,0.1)] text-[#eab308] border border-[rgba(234,179,8,0.2)]';
    case 'LOW':      return 'bg-[rgba(34,197,94,0.1)] text-[#22c55e] border border-[rgba(34,197,94,0.2)]';
    default:         return 'bg-[rgba(59,130,246,0.1)] text-[#3b82f6]';
  }
}

export function changeTypeClasses(ct: string): string {
  switch (ct) {
    case 'added':    return 'bg-[rgba(34,197,94,0.1)] text-[#22c55e] border border-[rgba(34,197,94,0.2)]';
    case 'modified': return 'bg-[rgba(234,179,8,0.1)] text-[#eab308] border border-[rgba(234,179,8,0.2)]';
    case 'deleted': case 'removed': return 'bg-[rgba(239,68,68,0.1)] text-[#ef4444] border border-[rgba(239,68,68,0.2)]';
    case 'renamed':  return 'bg-[rgba(59,130,246,0.1)] text-[#3b82f6] border border-[rgba(59,130,246,0.2)]';
    default:         return 'bg-[rgba(59,130,246,0.08)] text-[#5c5e6a]';
  }
}

export function changeTypePrefix(ct: string): string {
  switch (ct) {
    case 'added':    return 'A';
    case 'modified': return 'M';
    case 'deleted': case 'removed': return 'D';
    case 'renamed':  return 'R';
    default:         return '?';
  }
}

export function severityBadgeClasses(severity: string): string {
  switch (severity) {
    case 'critical': return 'bg-[rgba(239,68,68,0.1)] text-[#ef4444] border border-[rgba(239,68,68,0.2)]';
    case 'warning':  return 'bg-[rgba(234,179,8,0.1)] text-[#eab308] border border-[rgba(234,179,8,0.2)]';
    case 'info':     return 'bg-[rgba(59,130,246,0.1)] text-[#3b82f6] border border-[rgba(59,130,246,0.2)]';
    default:         return 'bg-[rgba(59,130,246,0.08)] text-[#5c5e6a]';
  }
}

export function shortId(id: string): string {
  const last = id.split('.').pop() || id;
  return last.split(':').pop() || last;
}

export function priorityBadgeClasses(p: string): string {
  switch (p) {
    case 'HIGH':   return 'bg-[rgba(239,68,68,0.1)] text-[#ef4444] border border-[rgba(239,68,68,0.2)]';
    case 'MEDIUM': return 'bg-[rgba(234,179,8,0.1)] text-[#eab308] border border-[rgba(234,179,8,0.2)]';
    case 'LOW':    return 'bg-[rgba(59,130,246,0.1)] text-[#3b82f6] border border-[rgba(59,130,246,0.2)]';
    default:       return 'bg-[rgba(59,130,246,0.08)] text-[#5c5e6a]';
  }
}
