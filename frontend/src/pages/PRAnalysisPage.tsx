import { useState } from 'react';
import { GitPullRequest, Search, GitCommitHorizontal, FileCode2, Layers, Zap, TestTube2, Shield } from 'lucide-react';
import { api } from '../services/api';
import type { PRAnalysisResult } from '../types/api';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorAlert } from '../components/ErrorAlert';
import { EmptyState } from '../components/EmptyState';
import { MetricCard } from '../components/MetricCard';
import { StatusBadge } from '../components/StatusBadge';
import { riskColor, riskBadgeClasses, changeTypeClasses, changeTypePrefix, shortId } from '../utils/helpers';

export default function PRAnalysisPage() {
  const [path, setPath] = useState('');
  const [baseCommit, setBaseCommit] = useState('');
  const [headCommit, setHeadCommit] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<PRAnalysisResult | null>(null);

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!path.trim() || !baseCommit.trim() || !headCommit.trim()) return;

    setIsLoading(true);
    setError(null);
    setData(null);
    try {
      const result = await api.analyzePR(path.trim(), baseCommit.trim(), headCommit.trim());
      setData(result);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 max-w-6xl mx-auto pb-12">
      
      {/* Header */}
      <div>
        <h1 className="sg-heading text-xl mb-1 flex items-center gap-2">
           <GitPullRequest size={20} className="text-[#a855f7]" /> Pull Request Analysis
        </h1>
        <p className="text-sm text-[#8b8d98]">Comprehensive pre-merge code intelligence and risk evaluation.</p>
      </div>

      {/* Form */}
      <div className="sg-panel p-4 sg-animate-in">
        <form onSubmit={handleAnalyze} className="flex flex-col md:flex-row gap-3 items-end">
          <div className="flex-1 w-full">
             <label className="block text-xs font-semibold text-[#8b8d98] mb-1.5">Repository Path</label>
             <input type="text" value={path} onChange={(e) => setPath(e.target.value)}
                placeholder="Absolute path..." className="sg-input w-full" />
          </div>
          <div className="w-full md:w-48">
             <label className="block text-xs font-semibold text-[#8b8d98] mb-1.5">Base Commit</label>
             <input type="text" value={baseCommit} onChange={(e) => setBaseCommit(e.target.value)}
                placeholder="e.g. main" className="sg-input w-full" />
          </div>
          <div className="w-full md:w-48">
             <label className="block text-xs font-semibold text-[#8b8d98] mb-1.5">Head Commit</label>
             <input type="text" value={headCommit} onChange={(e) => setHeadCommit(e.target.value)}
                placeholder="e.g. feature-branch" className="sg-input w-full" />
          </div>
          <button type="submit" disabled={isLoading || !path.trim() || !baseCommit.trim() || !headCommit.trim()} className="sg-btn sg-btn-primary w-full md:w-auto h-[35px]">
             <Search size={14} /> Analyze PR
          </button>
        </form>
      </div>

      {error && <ErrorAlert message={error} onRetry={() => handleAnalyze(new Event('submit') as unknown as React.FormEvent)} />}

      {isLoading ? (
        <LoadingSpinner message="Analyzing pull request (this may take a while)..." />
      ) : !data ? (
        <EmptyState title="No PR Data" description="Enter a repository path, base commit, and head commit to run PR intelligence." />
      ) : (
        <div className="flex flex-col gap-6 sg-animate-in">
          
          {/* Top Info Banner */}
          <div className="sg-panel flex flex-col md:flex-row items-center justify-between p-4 bg-[#1a1d24]">
             <div className="flex items-center gap-4 text-sm w-full md:w-auto mb-4 md:mb-0">
               <div className="flex flex-col">
                  <span className="text-[10px] uppercase font-bold text-[#5c5e6a]">Base</span>
                  <div className="flex items-center gap-2 mt-1">
                     <GitCommitHorizontal size={14} className="text-[#8b8d98]" />
                     <span className="font-mono font-medium text-[#e4e4e7]">{data.base_commit.short_hash}</span>
                  </div>
               </div>
               <div className="h-[2px] w-8 bg-[#2a2e38] relative">
                  <div className="absolute right-0 top-1/2 -translate-y-1/2 w-0 h-0 border-t-[3px] border-t-transparent border-l-[4px] border-l-[#2a2e38] border-b-[3px] border-b-transparent"></div>
               </div>
               <div className="flex flex-col">
                  <span className="text-[10px] uppercase font-bold text-[#5c5e6a]">Head</span>
                  <div className="flex items-center gap-2 mt-1">
                     <GitCommitHorizontal size={14} className="text-[#8b8d98]" />
                     <span className="font-mono font-medium text-[#e4e4e7]">{data.head_commit.short_hash}</span>
                  </div>
               </div>
             </div>
             
             <div className="flex items-center gap-8 border-t md:border-t-0 md:border-l border-[#2a2e38] pt-4 md:pt-0 md:pl-8 w-full md:w-auto">
               <div>
                 <div className="text-[10px] uppercase font-bold text-[#5c5e6a] mb-1">Merge Risk</div>
                 <div className="flex items-center gap-3">
                   <span className="text-2xl font-bold tracking-tight" style={{ color: riskColor(data.risk.level) }}>{data.risk.score}</span>
                   <StatusBadge label={data.risk.level} className={riskBadgeClasses(data.risk.level)} />
                 </div>
               </div>
               <div>
                 <div className="text-[10px] uppercase font-bold text-[#5c5e6a] mb-1">Diff Stats</div>
                 <div className="flex gap-3 text-sm font-mono">
                    <span className="text-[#22c55e]">+{data.total_additions}</span>
                    <span className="text-[#ef4444]">-{data.total_deletions}</span>
                 </div>
               </div>
             </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            {/* Main Column */}
            <div className="lg:col-span-2 flex flex-col gap-6">
              
              {/* Diff Summary */}
              <section className="sg-panel overflow-hidden">
                <div className="px-4 py-3 border-b border-[#2a2e38] bg-[#22262e] flex items-center justify-between">
                  <div className="sg-section-header mb-0 flex items-center gap-2">
                    <FileCode2 size={14} /> Changed Files
                  </div>
                  <span className="text-xs text-[#8b8d98]">{data.file_changes.length} files</span>
                </div>
                <div className="overflow-x-auto max-h-64">
                  <table className="sg-table">
                    <tbody className="font-mono text-xs">
                      {data.file_changes.map((fc, i) => (
                        <tr key={i}>
                          <td className="w-8 text-center px-2">
                            <span className={`inline-block w-4 h-4 text-center leading-4 rounded-sm font-bold ${changeTypeClasses(fc.change_type)}`}>
                              {changeTypePrefix(fc.change_type)}
                            </span>
                          </td>
                          <td className="text-[#e4e4e7] py-1.5">{fc.path}</td>
                          <td className="text-right text-[#22c55e] w-12">+{fc.additions}</td>
                          <td className="text-right text-[#ef4444] w-12 px-4">-{fc.deletions}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              {/* Component Changes */}
              <section className="sg-panel overflow-hidden">
                <div className="px-4 py-3 border-b border-[#2a2e38] bg-[#22262e] flex items-center justify-between">
                  <div className="sg-section-header mb-0 flex items-center gap-2">
                    <Layers size={14} /> Affected Components
                  </div>
                  <span className="text-xs text-[#8b8d98]">{data.changed_components.length} components</span>
                </div>
                <div className="overflow-x-auto max-h-64">
                  <table className="sg-table">
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Type</th>
                        <th>Change</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.changed_components.map((cc, i) => (
                        <tr key={i}>
                          <td className="font-mono text-[#e4e4e7]">{shortId(cc.component_id)}</td>
                          <td className="capitalize">{cc.component_type}</td>
                          <td><StatusBadge label={cc.change_type} className={changeTypeClasses(cc.change_type)} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              {/* Test Plan */}
              <section className="sg-panel p-5">
                <div className="sg-section-header mb-4 flex items-center gap-2">
                  <TestTube2 size={14} /> Recommended Test Plan
                </div>
                <div className="flex justify-between items-center bg-[#22262e] p-3 rounded mb-4 border border-[#2a2e38]">
                   <span className="text-sm font-medium text-[#e4e4e7]">
                     {data.test_selection.selected_tests} tests required ({data.test_selection.selection_percentage.toFixed(1)}% of suite)
                   </span>
                   <div className="flex gap-4 text-xs font-mono font-semibold">
                      <span className="text-[#ef4444]">H:{data.test_selection.high_priority.length}</span>
                      <span className="text-[#eab308]">M:{data.test_selection.medium_priority.length}</span>
                      <span className="text-[#3b82f6]">L:{data.test_selection.low_priority.length}</span>
                   </div>
                </div>
                
                {data.test_selection.selected_tests === 0 ? (
                  <p className="text-sm text-[#5c5e6a]">No tests matched this PR's blast radius.</p>
                ) : (
                  <div className="space-y-2">
                    {[...data.test_selection.high_priority, ...data.test_selection.medium_priority].slice(0, 10).map((ts, i) => (
                      <div key={i} className="flex items-center justify-between text-sm py-1.5 border-b border-[#2a2e38] last:border-0">
                         <span className="text-[#e4e4e7] truncate pr-4">{ts.test.test_name}</span>
                         <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${ts.priority === 'HIGH' ? 'bg-[#ef4444]/10 text-[#ef4444]' : 'bg-[#eab308]/10 text-[#eab308]'}`}>{ts.priority}</span>
                      </div>
                    ))}
                    {data.test_selection.selected_tests > 10 && (
                      <div className="text-xs text-[#5c5e6a] text-center pt-2">Showing top 10 highest priority tests.</div>
                    )}
                  </div>
                )}
              </section>

            </div>

            {/* Right Column (Impact / Complexity / Hotspots) */}
            <div className="flex flex-col gap-6">
              
              {/* Blast Radius Metrics */}
              <section className="sg-panel p-4">
                <div className="sg-section-header mb-3 flex items-center gap-2">
                  <Zap size={14} /> Impact Reach
                </div>
                <div className="grid grid-cols-2 gap-y-4 gap-x-2">
                  <MetricCard label="Direct" value={data.blast_radius.direct_impact_count} mono />
                  <MetricCard label="Transitive" value={data.blast_radius.transitive_impact_count} mono />
                  <MetricCard label="Total Impact" value={data.blast_radius.total_affected_count} mono />
                  <MetricCard label="APIs" value={data.blast_radius.affected_api_count} mono />
                </div>
              </section>

              {/* Complexity Delta */}
              {data.complexity_delta && (
                <section className="sg-panel p-4">
                  <div className="sg-section-header mb-3">Complexity Change</div>
                  <div className="flex justify-between items-center py-2 border-b border-[#2a2e38]">
                     <span className="text-sm text-[#8b8d98]">Avg Complexity</span>
                     <span className="font-mono text-sm text-[#e4e4e7]">
                        {data.complexity_delta.average_complexity_before.toFixed(1)} → {data.complexity_delta.average_complexity_after.toFixed(1)}
                     </span>
                  </div>
                  <div className="flex justify-between items-center py-2">
                     <span className="text-sm text-[#8b8d98]">Total Functions</span>
                     <span className="font-mono text-sm text-[#e4e4e7]">
                        {data.complexity_delta.total_functions_before} → {data.complexity_delta.total_functions_after}
                     </span>
                  </div>
                </section>
              )}

              {/* Hotspots Touched */}
              {data.hotspot_count > 0 && (
                <section className="sg-panel flex flex-col">
                  <div className="px-4 py-3 border-b border-[#2a2e38] bg-[#22262e]">
                     <div className="sg-section-header mb-0 flex items-center gap-2 text-[#ef4444]">
                       <Shield size={14} /> Hotspots Touched ({data.hotspot_count})
                     </div>
                  </div>
                  <div className="p-2 space-y-1">
                     {data.hotspots_touched.map((hs, i) => (
                       <div key={i} className="text-xs font-mono text-[#e4e4e7] p-2 bg-[#1a1d24] border border-transparent truncate">
                          {shortId(hs)}
                       </div>
                     ))}
                  </div>
                </section>
              )}

            </div>
          </div>
        </div>
      )}
    </div>
  );
}
