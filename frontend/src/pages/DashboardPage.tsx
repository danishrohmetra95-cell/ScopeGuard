import { useState } from 'react';
import {
  GitCommitHorizontal,
  Zap,
  TestTube2,
  AlertTriangle,
  TrendingUp,
  Play,
  ChevronDown,
  ChevronRight,
  History,
} from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { api } from '../services/api';
import type { FullAnalysisResult, RiskFactor } from '../types/api';
import { MetricCard } from '../components/MetricCard';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorAlert } from '../components/ErrorAlert';
import { EmptyState } from '../components/EmptyState';
import { StatusBadge } from '../components/StatusBadge';
import {
  riskColor,
  riskTextClass,
  riskBadgeClasses,
  severityBadgeClasses,
} from '../utils/helpers';

/* ── Horizontal Risk Scale ──────────────────────────────── */
function RiskScale({ score, level }: { score: number; level: string }) {
  const markerPosition = `${Math.min(Math.max(score, 0), 100)}%`;

  return (
    <div className="w-full mt-6 mb-2">
      <div className="flex justify-between text-xs font-semibold text-[#5c5e6a] mb-2 px-1">
        <span>LOW</span>
        <span>MEDIUM</span>
        <span>HIGH</span>
        <span>CRITICAL</span>
      </div>
      <div className="relative h-2 w-full rounded-full overflow-visible" style={{ background: 'var(--color-sg-border)' }}>
        {/* Gradients for each segment */}
        <div className="absolute top-0 left-0 h-full w-[25%] bg-[#22c55e] rounded-l-full opacity-60" />
        <div className="absolute top-0 left-[25%] h-full w-[25%] bg-[#eab308] opacity-60" />
        <div className="absolute top-0 left-[50%] h-full w-[25%] bg-[#f97316] opacity-60" />
        <div className="absolute top-0 left-[75%] h-full w-[25%] bg-[#ef4444] rounded-r-full opacity-60" />
        
        {/* Position Marker */}
        <div 
          className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 flex flex-col items-center"
          style={{ left: markerPosition, transition: 'left 0.5s ease' }}
        >
          <div className="w-3 h-3 rotate-45 border-2 border-[#1a1d24]" style={{ background: riskColor(level) }} />
        </div>
      </div>
    </div>
  );
}

/* ── Expandable Risk Factor Row ─────────────────────────── */
function RiskFactorRow({ factor }: { factor: RiskFactor }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border-b border-[#2a2e38] last:border-0">
      <div 
        className="flex items-start sm:items-center py-3 cursor-pointer hover:bg-[rgba(255,255,255,0.02)] px-2 -mx-2 rounded transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="mr-2 mt-0.5 sm:mt-0 text-[#5c5e6a]">
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </div>
        <div className="flex-1 min-w-0 pr-4">
          <div className="font-medium text-[#e4e4e7] truncate">{factor.name}</div>
        </div>
        <div className="w-24 text-right flex-shrink-0">
           <StatusBadge label={factor.severity} className={severityBadgeClasses(factor.severity)} />
        </div>
        <div className="w-16 text-right font-mono font-semibold text-[#e4e4e7] flex-shrink-0">
          +{factor.points}
        </div>
      </div>
      {expanded && (
        <div className="pl-6 pb-3 pr-2 text-sm text-[#8b8d98] leading-relaxed">
          {factor.description}
        </div>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const [repoPath, setRepoPath] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<FullAnalysisResult | null>(null);

  function isGitHubUrl(input: string): boolean {
    return /^https?:\/\/(www\.)?github\.com\/.+\/.+/i.test(input);
  }

  async function runAnalysis() {
    const trimmed = repoPath.trim();
    if (!trimmed) {
      setError('Please enter a repository path or GitHub URL.');
      return;
    }
    setLoading(true);
    setError(null);
    setData(null);
    try {
      if (isGitHubUrl(trimmed)) {
        const result = await api.analyzeGitHub(trimmed);
        setData(result);
      } else {
        const result = await api.analyzeFull(trimmed);
        setData(result);
      }
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axErr = err as { response?: { data?: { detail?: string } } };
        const detail = axErr.response?.data?.detail;
        if (detail) {
          setError(detail);
        } else {
          setError('Analysis failed. Check the backend connection.');
        }
      } else {
        const msg = err instanceof Error ? err.message : 'Analysis failed. Check backend connection.';
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }

  const riskScore = data?.risk.risk;
  const blast = data?.risk.blast_radius;
  const commit = data?.risk.commit;
  const testSel = data?.tests.test_selection;
  const trendPoints = data?.history.risk_trend ?? [];

  return (
    <div className="mx-auto max-w-6xl space-y-6 pb-12">
      {/* ── Input Bar ──────────────────────────────────────── */}
      <div className="sg-panel p-4 flex flex-col gap-3 sm:flex-row sm:items-center sg-animate-in">
        <div className="flex-1">
          <input
            id="repo-path"
            type="text"
            value={repoPath}
            onChange={(e) => setRepoPath(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && runAnalysis()}
            placeholder="Repository path (e.g., C:\my-repo or https://github.com/user/repo)"
            className="sg-input w-full"
          />
        </div>
        <button onClick={runAnalysis} disabled={loading} className="sg-btn sg-btn-primary flex-shrink-0">
          <Play size={14} />
          {loading ? 'Analyzing…' : 'Run Analysis'}
        </button>
      </div>

      {/* ── States ─────────────────────────────────────────── */}
      {loading && <LoadingSpinner message="Running comprehensive risk analysis…" />}
      {error && <ErrorAlert message={error} onRetry={runAnalysis} />}
      {!loading && !error && !data && (
        <EmptyState
          title="No analysis data"
          description="Enter a repository path or GitHub URL to analyze change impact and regression risk."
        />
      )}

      {/* ── Dashboard Results ──────────────────────────────── */}
      {data && riskScore && blast && commit && testSel && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 sg-animate-in">
          
          {/* Main Column (Risk & Details) */}
          <div className="lg:col-span-2 flex flex-col gap-6">
            
            {/* Risk Assessment Hero */}
            <section className="sg-panel p-6">
              <div className="flex justify-between items-start mb-6">
                <div>
                  <div className="sg-section-header">Risk Assessment</div>
                  <div className="flex items-baseline gap-3 mt-2">
                    <span className={`text-6xl font-bold tracking-tighter ${riskTextClass(riskScore.level)}`}>
                      {riskScore.score}
                    </span>
                    <span className="text-[#5c5e6a] text-lg">/ 100</span>
                  </div>
                  <div className="mt-2 flex items-center gap-2">
                    <StatusBadge label={riskScore.level} className={riskBadgeClasses(riskScore.level)} />
                  </div>
                </div>
                
                {/* Commit Context */}
                <div className="text-right flex flex-col items-end">
                  <div className="sg-section-header">Target Commit</div>
                  <div className="flex items-center gap-1.5 mt-2 bg-[#22262e] px-2 py-1 rounded border border-[#2a2e38]">
                    <GitCommitHorizontal size={14} className="text-[#8b8d98]" />
                    <span className="font-mono text-sm text-[#e4e4e7]">{commit.short_hash}</span>
                  </div>
                  <p className="text-xs text-[#8b8d98] mt-2">{commit.author}</p>
                </div>
              </div>
              
              <RiskScale score={riskScore.score} level={riskScore.level} />
              
              <div className="mt-6 pt-4 border-t border-[#2a2e38]">
                 <p className="text-sm text-[#8b8d98] leading-relaxed">{riskScore.summary}</p>
              </div>
            </section>

            {/* Why This Score */}
            <section className="sg-panel p-6">
              <div className="sg-section-header mb-4 flex items-center gap-2">
                <AlertTriangle size={14} /> Why This Score
              </div>
              {riskScore.factors.length === 0 ? (
                <p className="text-sm text-[#5c5e6a]">No significant risk factors identified.</p>
              ) : (
                <div className="flex flex-col">
                  {riskScore.factors.map((f, i) => (
                    <RiskFactorRow key={i} factor={f} />
                  ))}
                </div>
              )}
            </section>
            
            {/* Recommendations */}
            {riskScore.recommendations.length > 0 && (
              <section className="sg-panel p-6">
                <div className="sg-section-header mb-4 flex items-center gap-2">
                  <TrendingUp size={14} /> Actionable Recommendations
                </div>
                <ul className="space-y-3">
                  {riskScore.recommendations.map((rec, i) => (
                    <li key={i} className="flex items-start gap-3 text-sm text-[#e4e4e7]">
                      <span className="text-[#5c5e6a] font-mono mt-0.5">{i + 1}.</span>
                      <span className="leading-relaxed">{rec}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

          </div>

          {/* Right Column (Metrics & Context) */}
          <div className="flex flex-col gap-6">
            
            {/* Blast Radius */}
            <section className="sg-panel p-5">
              <div className="sg-section-header mb-4 flex items-center gap-2">
                <Zap size={14} /> Blast Radius
              </div>
              <div className="grid grid-cols-2 gap-4">
                <MetricCard label="Files" value={blast.changed_file_count} />
                <MetricCard label="Components" value={blast.changed_component_count} />
                <MetricCard label="Direct" value={blast.direct_impact_count} />
                <MetricCard label="Transitive" value={blast.transitive_impact_count} />
              </div>
              <div className="mt-4 pt-4 border-t border-[#2a2e38] flex justify-between items-center">
                <span className="text-sm text-[#8b8d98]">Affected APIs</span>
                <span className="font-mono text-base font-semibold text-[#e4e4e7]">{blast.affected_api_count}</span>
              </div>
            </section>

            {/* Test Selection */}
            <section className="sg-panel p-5">
              <div className="sg-section-header mb-4 flex items-center gap-2">
                <TestTube2 size={14} /> Test Selection
              </div>
              <div className="mb-4">
                <div className="text-3xl font-bold tracking-tight text-[#e4e4e7]">
                  {testSel.selected_tests} <span className="text-lg font-normal text-[#5c5e6a]">/ {testSel.total_tests}</span>
                </div>
                <div className="text-xs text-[#8b8d98] mt-1">Tests recommended ({testSel.selection_percentage.toFixed(1)}%)</div>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between items-center text-sm bg-[#22262e] p-2 rounded">
                  <span className="text-[#ef4444] font-medium flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-[#ef4444]" /> HIGH
                  </span>
                  <span className="font-mono">{testSel.high_priority.length}</span>
                </div>
                <div className="flex justify-between items-center text-sm bg-[#22262e] p-2 rounded">
                  <span className="text-[#eab308] font-medium flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-[#eab308]" /> MEDIUM
                  </span>
                  <span className="font-mono">{testSel.medium_priority.length}</span>
                </div>
                <div className="flex justify-between items-center text-sm bg-[#22262e] p-2 rounded">
                  <span className="text-[#3b82f6] font-medium flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-[#3b82f6]" /> LOW
                  </span>
                  <span className="font-mono">{testSel.low_priority.length}</span>
                </div>
              </div>
            </section>

            {/* History Trend */}
            {trendPoints.length > 0 && (
              <section className="sg-panel p-5">
                <div className="sg-section-header mb-4 flex items-center gap-2">
                  <History size={14} /> Risk Trend
                </div>
                <div className="h-32">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={trendPoints} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#2a2e38" />
                      <XAxis dataKey="commit_hash" hide />
                      <YAxis domain={[0, 100]} axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#5c5e6a' }} />
                      <Tooltip
                        contentStyle={{
                          background: '#1a1d24',
                          border: '1px solid #2a2e38',
                          borderRadius: '4px',
                          fontSize: '12px',
                        }}
                        itemStyle={{ color: '#e4e4e7' }}
                      />
                      <Line 
                        type="stepAfter" 
                        dataKey="score" 
                        stroke="#3b82f6" 
                        strokeWidth={2}
                        dot={false}
                        activeDot={{ r: 4, fill: '#3b82f6', stroke: '#1a1d24', strokeWidth: 2 }} 
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </section>
            )}
            
          </div>
        </div>
      )}
    </div>
  );
}
