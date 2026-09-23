import { useState } from 'react';
import { TestTube2, Search, Info } from 'lucide-react';
import { api } from '../services/api';
import type { CommitTestAnalysis } from '../types/api';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorAlert } from '../components/ErrorAlert';
import { EmptyState } from '../components/EmptyState';
import { shortId, priorityBadgeClasses } from '../utils/helpers';

export default function TestImpactPage() {
  const [path, setPath] = useState('');
  const [commit, setCommit] = useState('HEAD');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<CommitTestAnalysis | null>(null);

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!path.trim() || !commit.trim()) return;

    setIsLoading(true);
    setError(null);
    setData(null);
    try {
      const result = await api.analyzeCommitTests(path.trim(), commit.trim());
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
        <h1 className="sg-heading text-xl mb-1">Test Selection</h1>
        <p className="text-sm text-[#8b8d98]">Intelligently select tests to run based on code change blast radius.</p>
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
            <label className="block text-xs font-semibold text-[#8b8d98] mb-1.5">Commit Hash</label>
            <input type="text" value={commit} onChange={(e) => setCommit(e.target.value)}
              placeholder="HEAD" className="sg-input w-full" />
          </div>
          <button type="submit" disabled={isLoading || !path.trim()} className="sg-btn sg-btn-primary w-full md:w-auto">
            <Search size={14} /> Analyze Tests
          </button>
        </form>
      </div>

      {error && <ErrorAlert message={error} onRetry={() => handleAnalyze(new Event('submit') as unknown as React.FormEvent)} />}

      {isLoading ? (
        <LoadingSpinner message="Calculating test impact..." />
      ) : !data ? (
        <EmptyState title="No Test Analysis" description="Enter a repository path and commit hash to determine affected tests." />
      ) : (
        <div className="flex flex-col gap-6 sg-animate-in">
          
          {/* Static Analysis Warning */}
          <div className="bg-[#1e293b] border border-[#334155] rounded-md p-3 flex gap-3 text-sm">
            <Info size={16} className="text-[#3b82f6] mt-0.5 flex-shrink-0" />
            <div className="text-[#cbd5e1]">
              <strong className="text-[#e2e8f0]">Static Discovery:</strong> ScopeGuard identifies affected tests through static dependency analysis. It does not execute the test suite.
            </div>
          </div>

          {/* Metrics Summary Row */}
          <div className="sg-panel flex flex-col md:flex-row divide-y md:divide-y-0 md:divide-x divide-[#2a2e38]">
            <div className="p-6 flex-1 flex flex-col items-center justify-center">
              <div className="text-[11px] font-semibold text-[#8b8d98] uppercase tracking-wider mb-2">Selection Rate</div>
              <div className="text-4xl font-bold text-[#e4e4e7] tracking-tight">
                {data.test_selection.selection_percentage.toFixed(1)}%
              </div>
              <div className="text-sm text-[#5c5e6a] mt-1">{data.test_selection.selected_tests} of {data.test_selection.total_tests} tests</div>
            </div>
            
            <div className="p-6 flex-[2] grid grid-cols-3 gap-4">
               <div className="flex flex-col items-center justify-center">
                  <div className="text-3xl font-mono text-[#ef4444] mb-1">{data.test_selection.high_priority.length}</div>
                  <div className="text-xs font-semibold text-[#8b8d98]">HIGH PRIORITY</div>
               </div>
               <div className="flex flex-col items-center justify-center border-l border-r border-[#2a2e38]">
                  <div className="text-3xl font-mono text-[#eab308] mb-1">{data.test_selection.medium_priority.length}</div>
                  <div className="text-xs font-semibold text-[#8b8d98]">MEDIUM PRIORITY</div>
               </div>
               <div className="flex flex-col items-center justify-center">
                  <div className="text-3xl font-mono text-[#3b82f6] mb-1">{data.test_selection.low_priority.length}</div>
                  <div className="text-xs font-semibold text-[#8b8d98]">LOW PRIORITY</div>
               </div>
            </div>
          </div>

          {/* Test List Table */}
          <div className="sg-panel overflow-hidden">
            <div className="px-5 py-3 border-b border-[#2a2e38] bg-[#22262e] flex justify-between items-center">
              <h3 className="font-semibold text-[#e4e4e7] text-sm flex items-center gap-2">
                 <TestTube2 size={14} className="text-[#8b8d98]"/> Execution Plan
              </h3>
            </div>

            {data.test_selection.selected_tests === 0 ? (
              <div className="p-12 text-center text-[#5c5e6a] text-sm">
                No tests were selected for this commit. The changes do not affect any discovered tests.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="sg-table">
                  <thead>
                    <tr>
                      <th className="w-24">Priority</th>
                      <th className="w-1/4">Test Case</th>
                      <th>Selection Reason</th>
                      <th className="w-1/4">Affected Component</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      ...data.test_selection.high_priority,
                      ...data.test_selection.medium_priority,
                      ...data.test_selection.low_priority,
                    ].map((ts, idx) => (
                      <tr key={idx}>
                        <td>
                          <span className={`sg-badge ${priorityBadgeClasses(ts.priority)}`}>
                            {ts.priority}
                          </span>
                        </td>
                        <td>
                          <div className="font-medium text-[#e4e4e7] truncate" title={ts.test.test_name}>{ts.test.test_name}</div>
                          <div className="font-mono text-xs text-[#5c5e6a] truncate mt-0.5" title={ts.test.module_name}>{ts.test.module_name}</div>
                        </td>
                        <td className="text-[#8b8d98]">{ts.reason}</td>
                        <td>
                          <div className="flex flex-wrap gap-1">
                            {ts.affected_components.map((ac, i) => (
                              <span key={i} className="px-1.5 py-0.5 bg-[#1a1d24] border border-[#2a2e38] rounded text-[10px] font-mono text-[#5c5e6a]">
                                {shortId(ac)}
                              </span>
                            ))}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
