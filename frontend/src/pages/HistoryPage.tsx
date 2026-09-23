import { useState } from 'react';
import { TrendingUp, Flame, Search, Info } from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { api } from '../services/api';
import type { HistoricalAnalysisResult } from '../types/api';
import { MetricCard } from '../components/MetricCard';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorAlert } from '../components/ErrorAlert';
import { EmptyState } from '../components/EmptyState';
import { shortId } from '../utils/helpers';

export default function HistoryPage() {
  const [path, setPath] = useState('');
  const [limit, setLimit] = useState<number>(20);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<HistoricalAnalysisResult | null>(null);

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!path.trim()) return;
    setIsLoading(true);
    setError(null);
    setData(null);
    try {
      const result = await api.analyzeHistory(path.trim(), limit);
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
        <h1 className="sg-heading text-xl mb-1">Historical Analytics</h1>
        <p className="text-sm text-[#8b8d98]">Analyze commit history for risk trends, hotspots, and change intelligence.</p>
      </div>

      {/* Form */}
      <div className="sg-panel p-4 sg-animate-in">
        <form onSubmit={handleAnalyze} className="flex flex-col md:flex-row gap-3 items-end">
          <div className="flex-1 w-full">
             <label className="block text-xs font-semibold text-[#8b8d98] mb-1.5">Repository Path</label>
             <input type="text" value={path} onChange={(e) => setPath(e.target.value)}
                placeholder="Absolute path..." className="sg-input w-full" />
          </div>
          <div className="w-full md:w-32">
             <label className="block text-xs font-semibold text-[#8b8d98] mb-1.5">Limit (Commits)</label>
             <input type="number" min="1" max="100" value={limit}
                onChange={(e) => setLimit(parseInt(e.target.value) || 1)}
                className="sg-input w-full" />
          </div>
          <button type="submit" disabled={isLoading || !path.trim()} className="sg-btn sg-btn-primary w-full md:w-auto">
             <Search size={14} /> Analyze History
          </button>
        </form>
      </div>

      {error && <ErrorAlert message={error} onRetry={() => handleAnalyze(new Event('submit') as unknown as React.FormEvent)} />}

      {isLoading ? (
        <LoadingSpinner message={`Analyzing last ${limit} commits...`} />
      ) : !data ? (
        <EmptyState title="No Historical Data" description="Enter a repository path to analyze historical change intelligence and risk trends." />
      ) : (
        <div className="space-y-6 sg-animate-in">
          
          {/* Summary Banner */}
          <div className="sg-panel p-4 text-sm text-[#e4e4e7] leading-relaxed border-l-4 border-l-[#3b82f6]">
            {data.summary}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            {/* Risk Trend Chart */}
            <div className="lg:col-span-2 sg-panel p-5">
              <h3 className="sg-section-header mb-6 flex items-center gap-2">
                <TrendingUp size={14} /> Risk Trend
              </h3>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={data.risk_trend} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#2a2e38" />
                    <XAxis dataKey="commit_hash" hide />
                    <YAxis domain={[0, 100]} axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#5c5e6a' }} />
                    <Tooltip
                      contentStyle={{ background: '#1a1d24', border: '1px solid #2a2e38', borderRadius: '4px', fontSize: '12px' }}
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
            </div>

            {/* Insights */}
            <div className="sg-panel flex flex-col">
              <div className="px-4 py-3 border-b border-[#2a2e38] bg-[#22262e]">
                 <h3 className="sg-section-header mb-0 flex items-center gap-2">
                   <Info size={14} /> Deterministic Insights
                 </h3>
              </div>
              <div className="p-4 flex-1 overflow-y-auto">
                <ul className="space-y-3">
                  {data.insights.map((insight, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-sm text-[#8b8d98]">
                      <span className="text-[#5c5e6a] mt-0.5">•</span>
                      <span className="leading-relaxed">{insight}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>

          {/* Risk Distribution */}
          <div className="sg-panel p-4">
            <h3 className="sg-section-header mb-4">Risk Distribution</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <MetricCard label="LOW Commits" value={data.risk_trend_summary.low_count} />
              <MetricCard label="MEDIUM Commits" value={data.risk_trend_summary.medium_count} />
              <MetricCard label="HIGH Commits" value={data.risk_trend_summary.high_count} />
              <MetricCard label="CRITICAL Commits" value={data.risk_trend_summary.critical_count} />
            </div>
          </div>

          {/* Hotspots */}
          <div className="sg-panel overflow-hidden">
            <div className="px-4 py-3 border-b border-[#2a2e38] bg-[#22262e] flex items-center justify-between">
              <h3 className="sg-section-header mb-0 flex items-center gap-2">
                <Flame size={14} className="text-[#ef4444]" /> Top Component Hotspots
              </h3>
            </div>

            {data.component_hotspots.length === 0 ? (
              <div className="p-8 text-center text-[#5c5e6a] text-sm">No component hotspots found.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="sg-table">
                  <thead>
                    <tr>
                      <th className="w-1/3">Component</th>
                      <th>Changes</th>
                      <th>Avg Risk</th>
                      <th>Max Risk</th>
                      <th className="w-1/4">Hotspot Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.component_hotspots.slice(0, 10).map((h, idx) => {
                      const maxScore = data.component_hotspots[0]?.hotspot_score || 1;
                      const pct = (h.hotspot_score / maxScore) * 100;
                      return (
                        <tr key={idx}>
                          <td className="font-mono text-[#e4e4e7] truncate" title={h.component_id}>{shortId(h.component_id)}</td>
                          <td className="text-[#e4e4e7]">
                            {h.change_count}
                            <span className="text-xs text-[#5c5e6a] ml-2">
                              (M:{h.modification_count} A:{h.addition_count} D:{h.removal_count})
                            </span>
                          </td>
                          <td className="text-[#8b8d98] font-mono">{h.average_risk.toFixed(1)}</td>
                          <td className="text-[#e4e4e7] font-mono">{h.max_risk}</td>
                          <td>
                            <div className="flex items-center gap-2">
                              <div className="flex-1 h-1.5 bg-[#2a2e38] rounded-full overflow-hidden">
                                <div className="h-full bg-[#ef4444] rounded-full" style={{ width: `${pct}%` }} />
                              </div>
                              <span className="text-xs font-mono font-semibold text-[#e4e4e7] w-8 text-right">
                                {h.hotspot_score.toFixed(1)}
                              </span>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
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
