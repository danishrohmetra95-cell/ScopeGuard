import { useState } from 'react';
import { Search, GitCommitHorizontal, Shield, FileCode2, Layers, Zap } from 'lucide-react';
import { api } from '../services/api';
import type { CommitRiskAnalysis } from '../types/api';
import { MetricCard } from '../components/MetricCard';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorAlert } from '../components/ErrorAlert';
import { EmptyState } from '../components/EmptyState';
import { StatusBadge } from '../components/StatusBadge';
import {
  riskColor,
  riskBadgeClasses,
  changeTypeClasses,
  changeTypePrefix,
  shortId,
} from '../utils/helpers';

export default function CommitAnalysisPage() {
  const [repoPath, setRepoPath] = useState('');
  const [commitHash, setCommitHash] = useState('HEAD');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<CommitRiskAnalysis | null>(null);

  async function handleAnalyze() {
    if (!repoPath.trim()) return;
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const result = await api.analyzeCommitRisk(repoPath.trim(), commitHash.trim() || 'HEAD');
      setData(result);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Analysis failed';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-12">
      {/* ── Header ────────────────────────────────────────── */}
      <div>
        <h1 className="sg-heading text-xl mb-1">Commit Analysis</h1>
        <p className="text-sm text-[#8b8d98]">Detailed breakdown of code changes, impact, and risk.</p>
      </div>

      {/* ── Input Form ────────────────────────────────────── */}
      <div className="sg-panel p-4 flex flex-col sm:flex-row gap-3 items-end sg-animate-in">
        <div className="flex-1 w-full">
          <label htmlFor="repo-path" className="block text-xs font-semibold text-[#8b8d98] mb-1.5">
            Repository Path
          </label>
          <input id="repo-path" type="text" placeholder="/path/to/repository"
            value={repoPath} onChange={(e) => setRepoPath(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAnalyze()}
            className="sg-input w-full" />
        </div>
        <div className="w-full sm:w-48">
          <label htmlFor="commit-hash" className="block text-xs font-semibold text-[#8b8d98] mb-1.5">
            Commit Hash
          </label>
          <input id="commit-hash" type="text" placeholder="HEAD"
            value={commitHash} onChange={(e) => setCommitHash(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAnalyze()}
            className="sg-input w-full" />
        </div>
        <button onClick={handleAnalyze} disabled={loading || !repoPath.trim()}
          className="sg-btn sg-btn-primary w-full sm:w-auto h-[35px]">
          <Search size={14} />
          Analyze
        </button>
      </div>

      {/* ── States ────────────────────────────────────────── */}
      {loading && <LoadingSpinner message="Analyzing commit…" />}
      {error && <ErrorAlert message={error} onRetry={handleAnalyze} />}
      {!loading && !error && !data && (
        <EmptyState title="No Analysis Data" description="Enter a repository path and commit hash to begin analysis." />
      )}

      {/* ── Results ───────────────────────────────────────── */}
      {data && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 sg-animate-in">
          
          {/* Main Content Column */}
          <div className="lg:col-span-2 flex flex-col gap-6">
            
            {/* Commit Header */}
            <section className="sg-panel p-5">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <GitCommitHorizontal size={16} className="text-[#5c5e6a]" />
                    <span className="font-mono font-semibold text-[#e4e4e7] text-lg">{data.commit.short_hash}</span>
                  </div>
                  <h2 className="text-[#e4e4e7] font-medium leading-snug">{data.commit.message}</h2>
                  <div className="mt-4 text-xs text-[#8b8d98] flex items-center gap-4">
                    <span>{data.commit.author}</span>
                    <span>{new Date(data.commit.timestamp).toLocaleString()}</span>
                  </div>
                </div>
                <div className="text-right">
                   <div className="text-3xl font-bold tracking-tight mb-1" style={{ color: riskColor(data.risk.level) }}>
                     {data.risk.score}
                   </div>
                   <StatusBadge label={data.risk.level} className={riskBadgeClasses(data.risk.level)} />
                </div>
              </div>
            </section>

            {/* Changed Files */}
            {data.file_changes.length > 0 && (
              <section className="sg-panel overflow-hidden">
                <div className="px-4 py-3 border-b border-[#2a2e38] bg-[#22262e] flex items-center justify-between">
                  <div className="flex items-center gap-2 font-medium text-sm">
                    <FileCode2 size={14} className="text-[#8b8d98]" /> File Changes
                  </div>
                  <span className="text-xs text-[#8b8d98]">{data.file_changes.length} files</span>
                </div>
                <div className="overflow-x-auto">
                  <table className="sg-table">
                    <tbody className="font-mono text-xs">
                      {data.file_changes.map((fc, i) => (
                        <tr key={i}>
                          <td className="w-8 text-center px-2">
                            <span className={`inline-block w-4 h-4 text-center leading-4 rounded-sm font-bold ${changeTypeClasses(fc.change_type)}`}>
                              {changeTypePrefix(fc.change_type)}
                            </span>
                          </td>
                          <td className="text-[#e4e4e7] py-2">{fc.path}</td>
                          <td className="text-right text-[#22c55e] w-16">+{fc.additions}</td>
                          <td className="text-right text-[#ef4444] w-16 px-4">-{fc.deletions}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}

            {/* Changed Components */}
            {data.changed_components.length > 0 && (
              <section className="sg-panel overflow-hidden">
                <div className="px-4 py-3 border-b border-[#2a2e38] bg-[#22262e] flex items-center justify-between">
                  <div className="flex items-center gap-2 font-medium text-sm">
                    <Layers size={14} className="text-[#8b8d98]" /> Affected Components
                  </div>
                  <span className="text-xs text-[#8b8d98]">{data.changed_components.length} components</span>
                </div>
                <div className="overflow-x-auto">
                  <table className="sg-table">
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Type</th>
                        <th>Change</th>
                        <th>Semantics</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.changed_components.map((cc, i) => (
                        <tr key={i}>
                          <td className="font-mono text-[#e4e4e7]">{shortId(cc.component_id)}</td>
                          <td className="capitalize">{cc.component_type}</td>
                          <td>
                            <StatusBadge label={cc.change_type} className={changeTypeClasses(cc.change_type)} />
                          </td>
                          <td>
                            <span className="text-xs text-[#8b8d98]">{cc.change_semantics || '-'}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}
          </div>

          {/* Right Sidebar Column */}
          <div className="flex flex-col gap-6">
            
            {/* Blast Radius Summary */}
            <section className="sg-panel p-4">
              <div className="sg-section-header mb-3 flex items-center gap-2">
                <Zap size={14} /> Impact Summary
              </div>
              <div className="grid grid-cols-2 gap-y-4 gap-x-2">
                <MetricCard label="Direct" value={data.blast_radius.direct_impact_count} mono />
                <MetricCard label="Transitive" value={data.blast_radius.transitive_impact_count} mono />
                <MetricCard label="Total Reach" value={data.blast_radius.total_affected_count} mono />
                <MetricCard label="APIs" value={data.blast_radius.affected_api_count} mono />
              </div>
            </section>

            {/* Direct Impact List */}
            {data.direct_impact.length > 0 && (
              <section className="sg-panel flex flex-col max-h-96">
                <div className="px-4 py-3 border-b border-[#2a2e38] bg-[#22262e]">
                  <div className="text-sm font-medium flex items-center gap-2">Direct Dependents</div>
                </div>
                <div className="overflow-y-auto p-2 space-y-1">
                  {data.direct_impact.map((item, i) => (
                    <div key={i} className="p-2 hover:bg-[#22262e] rounded text-xs font-mono text-[#8b8d98] break-all">
                      {shortId(item.component_id)}
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Risk Factors Summary */}
            {data.risk.factors.length > 0 && (
              <section className="sg-panel flex flex-col">
                <div className="px-4 py-3 border-b border-[#2a2e38] bg-[#22262e]">
                  <div className="text-sm font-medium flex items-center gap-2">
                    <Shield size={14} className="text-[#8b8d98]"/> Risk Drivers
                  </div>
                </div>
                <div className="p-0">
                  <table className="sg-table">
                    <tbody>
                      {data.risk.factors.map((f, i) => (
                        <tr key={i}>
                          <td className="text-[#e4e4e7] py-2">{f.name}</td>
                          <td className="text-right w-12 text-[#e4e4e7] font-mono">+{f.points}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}

          </div>
        </div>
      )}
    </div>
  );
}
