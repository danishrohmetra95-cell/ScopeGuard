import { useState } from 'react';
import { Beaker, Search, Shield, Zap, AlertTriangle, Network, Info } from 'lucide-react';
import { api } from '../services/api';
import type { WhatIfResult } from '../types/api';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorAlert } from '../components/ErrorAlert';
import { EmptyState } from '../components/EmptyState';
import { MetricCard } from '../components/MetricCard';
import { StatusBadge } from '../components/StatusBadge';
import { riskColor, riskBadgeClasses, shortId } from '../utils/helpers';

export default function WhatIfPage() {
  const [path, setPath] = useState('');
  const [componentId, setComponentId] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<WhatIfResult | null>(null);

  const handleSimulate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!path.trim() || !componentId.trim()) return;

    setIsLoading(true);
    setError(null);
    setData(null);
    try {
      const result = await api.analyzeWhatIf(path.trim(), componentId.trim());
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
           <Beaker size={20} className="text-[#3b82f6]" /> What-If Simulator
        </h1>
        <p className="text-sm text-[#8b8d98]">Predict blast radius and regression risk before writing any code.</p>
      </div>

      {/* Form */}
      <div className="sg-panel p-4 sg-animate-in">
        <form onSubmit={handleSimulate} className="flex flex-col md:flex-row gap-3 items-end">
          <div className="flex-1 w-full">
             <label className="block text-xs font-semibold text-[#8b8d98] mb-1.5">Repository Path</label>
             <input type="text" value={path} onChange={(e) => setPath(e.target.value)}
                placeholder="Absolute path..." className="sg-input w-full" />
          </div>
          <div className="flex-1 w-full">
             <label className="block text-xs font-semibold text-[#8b8d98] mb-1.5">Component ID (Function/Class/Method)</label>
             <input type="text" value={componentId} onChange={(e) => setComponentId(e.target.value)}
                placeholder="e.g. function:backend.api.login" className="sg-input w-full" />
          </div>
          <button type="submit" disabled={isLoading || !path.trim() || !componentId.trim()} className="sg-btn sg-btn-primary w-full md:w-auto h-[35px]">
             <Search size={14} /> Simulate Impact
          </button>
        </form>
      </div>

      {error && <ErrorAlert message={error} onRetry={() => handleSimulate(new Event('submit') as unknown as React.FormEvent)} />}

      {isLoading ? (
        <LoadingSpinner message="Running static simulation..." />
      ) : !data ? (
        <EmptyState title="No Simulation Data" description="Enter a repository path and a component ID to simulate a change." />
      ) : (
        <div className="flex flex-col gap-6 sg-animate-in">
          
          {/* Simulation Disclaimer */}
          <div className="bg-[#2a1b10] border border-[#4d2d18] rounded-md p-3 flex gap-3 text-sm">
            <AlertTriangle size={16} className="text-[#f97316] mt-0.5 flex-shrink-0" />
            <div className="text-[#e4e4e7]">
              <strong className="text-[#f97316]">SIMULATION ONLY:</strong> {data.disclaimer}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            {/* Target Component & Risk */}
            <div className="lg:col-span-2 flex flex-col gap-6">
              <section className="sg-panel p-6">
                 <div className="flex justify-between items-start">
                   <div>
                     <div className="sg-section-header">Target Component</div>
                     <div className="font-mono text-lg text-[#e4e4e7] mt-1 break-all">{data.component_name || shortId(data.component_id)}</div>
                     <div className="flex items-center gap-3 mt-2 text-sm text-[#8b8d98]">
                        <span className="capitalize border border-[#2a2e38] px-2 py-0.5 rounded text-xs bg-[#22262e]">{data.component_type || 'Unknown'}</span>
                        {data.file_path && <span>{data.file_path}</span>}
                     </div>
                   </div>
                   
                   <div className="text-right flex flex-col items-end">
                     <div className="sg-section-header">Predicted Risk</div>
                     <div className="text-5xl font-bold tracking-tight mt-1 mb-2" style={{ color: riskColor(data.predicted_risk_level) }}>
                       {data.predicted_risk_score}
                     </div>
                     <StatusBadge label={data.predicted_risk_level} className={riskBadgeClasses(data.predicted_risk_level)} />
                   </div>
                 </div>
              </section>

              {/* Blast Radius Summary */}
              <section className="sg-panel p-5">
                <div className="sg-section-header mb-4 flex items-center gap-2">
                  <Zap size={14} /> Predicted Blast Radius
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <MetricCard label="Direct Impact" value={data.blast_radius.direct_impact_count} mono />
                  <MetricCard label="Transitive Impact" value={data.blast_radius.transitive_impact_count} mono />
                  <MetricCard label="Total Reach" value={data.blast_radius.total_affected_count} mono />
                  <MetricCard label="Affected APIs" value={data.blast_radius.affected_api_count} mono />
                </div>
              </section>

              {/* Recommendations */}
              {data.recommendations.length > 0 && (
                <section className="sg-panel p-5">
                  <div className="sg-section-header mb-4 flex items-center gap-2">
                    <Info size={14} /> Pre-Commit Recommendations
                  </div>
                  <ul className="space-y-2">
                    {data.recommendations.map((rec, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-[#e4e4e7]">
                        <span className="text-[#5c5e6a] font-mono mt-0.5">{i + 1}.</span>
                        <span className="leading-relaxed">{rec}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </div>

            {/* Right Column: APIs & Tests */}
            <div className="flex flex-col gap-6">
               
               {/* Affected APIs */}
               <section className="sg-panel flex flex-col max-h-96">
                 <div className="px-4 py-3 border-b border-[#2a2e38] bg-[#22262e]">
                    <div className="sg-section-header mb-0 flex items-center gap-2">
                      <Network size={14} /> Affected APIs ({data.affected_apis.length})
                    </div>
                 </div>
                 <div className="overflow-y-auto p-2">
                   {data.affected_apis.length === 0 ? (
                     <div className="p-4 text-center text-[#5c5e6a] text-xs">No public APIs affected.</div>
                   ) : (
                     <div className="space-y-1">
                       {data.affected_apis.map((api, i) => (
                         <div key={i} className="p-2 hover:bg-[#22262e] rounded border border-transparent hover:border-[#2a2e38]">
                            <div className="flex items-center gap-2 mb-1">
                              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                                api.http_method === 'GET' ? 'bg-[#3b82f6]/20 text-[#3b82f6]' :
                                api.http_method === 'POST' ? 'bg-[#22c55e]/20 text-[#22c55e]' :
                                'bg-[#8b8d98]/20 text-[#8b8d98]'
                              }`}>{api.http_method}</span>
                              <span className="font-mono text-xs text-[#e4e4e7] truncate" title={api.route_path || ''}>{api.route_path || 'Unknown Route'}</span>
                            </div>
                            <div className="text-[10px] text-[#5c5e6a] font-mono truncate">{api.function_name}</div>
                         </div>
                       ))}
                     </div>
                   )}
                 </div>
               </section>

               {/* Affected Tests */}
               <section className="sg-panel flex flex-col max-h-96">
                 <div className="px-4 py-3 border-b border-[#2a2e38] bg-[#22262e]">
                    <div className="sg-section-header mb-0 flex items-center gap-2">
                      <Shield size={14} /> Recommended Tests ({data.affected_tests.length})
                    </div>
                 </div>
                 <div className="overflow-y-auto p-2">
                   {data.affected_tests.length === 0 ? (
                     <div className="p-4 text-center text-[#5c5e6a] text-xs">No tests matched this blast radius.</div>
                   ) : (
                     <div className="space-y-1">
                       {data.affected_tests.map((test, i) => (
                         <div key={i} className="p-2 hover:bg-[#22262e] rounded border border-transparent hover:border-[#2a2e38]">
                            <div className="font-medium text-xs text-[#e4e4e7] truncate" title={test.test_name}>{test.test_name}</div>
                            <div className="flex justify-between items-center mt-1">
                               <span className="text-[10px] text-[#8b8d98] font-mono truncate max-w-[70%]" title={test.test_file}>{test.test_file}</span>
                               <span className={`text-[10px] font-bold ${
                                 test.priority === 'HIGH' ? 'text-[#ef4444]' :
                                 test.priority === 'MEDIUM' ? 'text-[#eab308]' : 'text-[#3b82f6]'
                               }`}>{test.priority}</span>
                            </div>
                         </div>
                       ))}
                     </div>
                   )}
                 </div>
               </section>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
