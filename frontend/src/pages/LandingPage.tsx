import { Link } from 'react-router-dom';
import { ArrowRight, GitCommitHorizontal, Network, Zap, ShieldAlert, TestTube2 } from 'lucide-react';

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#111318] text-[#e4e4e7] flex flex-col font-sans selection:bg-[#3b82f6]/30">
      
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-6 border-b border-transparent">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded border border-[#2a2e38] bg-[#1a1d24] flex items-center justify-center">
            <span className="font-mono text-sm font-bold text-[#e4e4e7]">SG</span>
          </div>
          <div className="flex flex-col">
            <span className="font-mono font-bold tracking-tight text-sm leading-none">SCOPEGUARD</span>
            <span className="font-mono text-[10px] text-[#5c5e6a] mt-0.5">STATIC ANALYSIS ENGINE</span>
          </div>
        </div>
      </header>

      {/* Main Hero */}
      <main className="flex-1 flex flex-col items-center justify-center px-4 md:px-8 max-w-6xl mx-auto w-full">
        
        <div className="flex flex-col lg:flex-row items-center gap-16 w-full">
          
          {/* Left: Text Content */}
          <div className="flex-1 flex flex-col items-start text-left z-10 w-full">
            <div className="font-mono text-xs font-semibold tracking-wider text-[#3b82f6] mb-4 uppercase border border-[#3b82f6]/20 bg-[#3b82f6]/5 px-2 py-1 rounded">
              Dependency-Aware Code Intelligence
            </div>
            
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-semibold tracking-tight text-[#e4e4e7] leading-[1.1] mb-6">
              Understand the impact <br className="hidden md:block" />
              <span className="text-[#8b8d98]">before you merge.</span>
            </h1>
            
            <p className="text-base md:text-lg text-[#8b8d98] mb-6 max-w-xl leading-relaxed">
              ScopeGuard maps code dependencies, evaluates regression risk, and identifies the tests that actually matter.
            </p>

            <div className="font-mono text-[10px] text-[#5c5e6a] tracking-widest mb-10 flex flex-wrap gap-2 items-center">
              <span>STATIC ANALYSIS</span>
              <span className="text-[#3b82f6]">&rarr;</span>
              <span>DEPENDENCY GRAPH</span>
              <span className="text-[#3b82f6]">&rarr;</span>
              <span>IMPACT ANALYSIS</span>
              <span className="text-[#3b82f6]">&rarr;</span>
              <span>RISK</span>
              <span className="text-[#3b82f6]">&rarr;</span>
              <span>TEST IMPACT</span>
            </div>
            
            <Link 
              to="/dashboard"
              className="inline-flex items-center justify-center gap-2 bg-[#e4e4e7] text-[#111318] hover:bg-white px-6 py-3 rounded text-sm font-bold transition-colors focus:outline-none focus:ring-2 focus:ring-[#3b82f6] focus:ring-offset-2 focus:ring-offset-[#111318]"
            >
              ENTER SCOPE <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          {/* Right: Technical Visualization */}
          <div className="flex-1 w-full max-w-md lg:max-w-none flex flex-col items-center lg:items-end">
            <div className="relative w-full max-w-sm border border-[#2a2e38] rounded bg-[#1a1d24] p-8 shadow-2xl mb-4">
              
              {/* Node Sequence Pipeline */}
              <div className="flex flex-col gap-6 relative">
                
                {/* Continuous Vertical Line */}
                <div className="absolute left-[19px] top-4 bottom-4 w-px bg-gradient-to-b from-transparent via-[#2a2e38] to-transparent z-0"></div>

                {/* Change */}
                <div className="flex items-start gap-4 relative z-10 group">
                  <div className="w-10 h-10 rounded-full border border-[#2a2e38] bg-[#22262e] flex items-center justify-center text-[#3b82f6] shrink-0 transition-colors group-hover:border-[#3b82f6]">
                    <GitCommitHorizontal className="w-4 h-4" />
                  </div>
                  <div className="pt-1.5 flex-1">
                    <div className="font-mono text-xs font-semibold text-[#e4e4e7] mb-1 tracking-wide">CHANGE</div>
                    <div className="text-[11px] text-[#5c5e6a] leading-snug">Code changes enter ScopeGuard</div>
                  </div>
                </div>

                {/* Dependencies */}
                <div className="flex items-start gap-4 relative z-10 group">
                  <div className="w-10 h-10 rounded-full border border-[#2a2e38] bg-[#22262e] flex items-center justify-center text-[#e4e4e7] shrink-0 transition-colors group-hover:border-[#e4e4e7]">
                    <Network className="w-4 h-4" />
                  </div>
                  <div className="pt-1.5 flex-1">
                    <div className="font-mono text-xs font-semibold text-[#e4e4e7] mb-1 tracking-wide">DEPENDENCIES</div>
                    <div className="text-[11px] text-[#5c5e6a] leading-snug">Dependency relationships resolved</div>
                  </div>
                </div>

                {/* Blast Radius */}
                <div className="flex items-start gap-4 relative z-10 group">
                  <div className="w-10 h-10 rounded-full border border-[#2a2e38] bg-[#22262e] flex items-center justify-center text-[#f97316] shrink-0 transition-colors group-hover:border-[#f97316]">
                    <Zap className="w-4 h-4" />
                  </div>
                  <div className="pt-1.5 flex-1">
                    <div className="font-mono text-xs font-semibold text-[#e4e4e7] mb-1 tracking-wide">BLAST RADIUS</div>
                    <div className="text-[11px] text-[#5c5e6a] leading-snug">Transitive impact calculated</div>
                  </div>
                </div>

                {/* Risk */}
                <div className="flex items-start gap-4 relative z-10 group">
                  <div className="w-10 h-10 rounded-full border border-[#ef4444]/30 bg-[#ef4444]/10 flex items-center justify-center text-[#ef4444] shrink-0 transition-colors group-hover:border-[#ef4444]">
                    <ShieldAlert className="w-4 h-4" />
                  </div>
                  <div className="pt-1.5 flex-1">
                    <div className="font-mono text-xs font-semibold text-[#ef4444] mb-1 tracking-wide">RISK</div>
                    <div className="text-[11px] text-[#5c5e6a] leading-snug text-[#ef4444]/70">Risk evaluates deterministically</div>
                  </div>
                </div>

                {/* Test Impact */}
                <div className="flex items-start gap-4 relative z-10 group">
                  <div className="w-10 h-10 rounded-full border border-[#2a2e38] bg-[#22262e] flex items-center justify-center text-[#22c55e] shrink-0 transition-colors group-hover:border-[#22c55e]">
                    <TestTube2 className="w-4 h-4" />
                  </div>
                  <div className="pt-1.5 flex-1">
                    <div className="font-mono text-xs font-semibold text-[#e4e4e7] mb-1 tracking-wide">TEST IMPACT</div>
                    <div className="text-[11px] text-[#5c5e6a] leading-snug">Relevant tests identified</div>
                  </div>
                </div>

              </div>
            </div>

            {/* Analysis Model Detail */}
            <div className="w-full max-w-sm flex items-center justify-center font-mono text-[9px] sm:text-[10px] text-[#5c5e6a] tracking-widest border border-[#2a2e38]/50 bg-[#1a1d24]/50 px-4 py-2 rounded">
              READ-ONLY ANALYSIS &nbsp;|&nbsp; AST + GRAPH TRAVERSAL &nbsp;|&nbsp; NO CODE EXECUTION
            </div>
          </div>
          
        </div>
      </main>

      {/* Footer Capability Strip */}
      <footer className="w-full border-t border-[#2a2e38] bg-[#1a1d24]">
        <div className="max-w-6xl mx-auto px-6 py-4 flex flex-wrap items-center justify-center md:justify-between gap-4 md:gap-8">
          {['AST ANALYSIS', 'DEPENDENCY GRAPH', 'IMPACT ANALYSIS', 'RISK ENGINE', 'TEST IMPACT', 'CI/CD'].map((label) => (
            <div key={label} className="font-mono text-[10px] sm:text-xs text-[#5c5e6a] font-medium tracking-widest flex items-center gap-2">
              <span className="w-1 h-1 rounded-full bg-[#3b82f6]/50"></span>
              {label}
            </div>
          ))}
        </div>
      </footer>

    </div>
  );
}
