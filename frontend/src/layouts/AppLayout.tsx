import { NavLink, Outlet, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  GitCommitHorizontal,
  Network,
  TestTube2,
  History,
  Activity,
  ChevronLeft,
  ChevronRight,
  Menu,
  GitPullRequest,
  Beaker
} from 'lucide-react';
import { useState, useEffect } from 'react';

const navItems = [
  { to: '/', label: 'Overview', icon: LayoutDashboard },
  { to: '/commit', label: 'Commit Analysis', icon: GitCommitHorizontal },
  { to: '/graph', label: 'Dependency Graph', icon: Network },
  { to: '/tests', label: 'Test Selection', icon: TestTube2 },
  { to: '/history', label: 'History', icon: History },
  { to: '/whatif', label: 'What-If Simulator', icon: Beaker },
  { to: '/pr', label: 'Pull Request', icon: GitPullRequest },
];

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();

  // Close mobile menu on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  // Handle responsive collapse
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 1024 && window.innerWidth >= 768) {
        setCollapsed(true);
      } else if (window.innerWidth >= 1024) {
        setCollapsed(false);
      }
    };
    window.addEventListener('resize', handleResize);
    handleResize(); // Initial check
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const getPageTitle = () => {
    const route = navItems.find(item => 
      item.to === '/' ? location.pathname === '/' : location.pathname.startsWith(item.to)
    );
    return route ? route.label : 'Dashboard';
  };

  return (
    <div className="min-h-screen flex text-sm text-[#e4e4e7] bg-[#111318]">
      
      {/* Mobile Overlay */}
      {mobileOpen && (
        <div 
          className="fixed inset-0 z-40 bg-black/50 md:hidden" 
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed md:sticky top-0 z-50 flex flex-col h-screen transition-all duration-150 ease-in-out
          bg-[#1a1d24] border-r border-[#2a2e38]
          ${mobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
        `}
        style={{ width: collapsed ? '48px' : '220px' }}
      >
        {/* Logo Area */}
        <div className="h-12 flex items-center px-3 border-b border-[#2a2e38] flex-shrink-0">
          <div className="w-6 h-6 rounded bg-[#22262e] border border-[#2a2e38] flex items-center justify-center flex-shrink-0">
            <span className="text-xs font-bold text-[#e4e4e7]">SG</span>
          </div>
          {!collapsed && (
            <span className="ml-3 font-semibold tracking-tight">ScopeGuard</span>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4 flex flex-col gap-1 px-2 overflow-y-auto overflow-x-hidden">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) => `
                flex items-center gap-3 px-2 py-1.5 rounded transition-colors group
                ${isActive 
                  ? 'bg-[#22262e] text-[#e4e4e7] border-l-2 border-[#3b82f6]' 
                  : 'text-[#8b8d98] hover:bg-[#22262e] hover:text-[#e4e4e7] border-l-2 border-transparent'
                }
              `}
              title={collapsed ? label : undefined}
            >
              <Icon className="h-4 w-4 flex-shrink-0" />
              {!collapsed && <span className="truncate">{label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* Footer Controls */}
        <div className="p-2 border-t border-[#2a2e38] flex flex-col gap-2">
          {/* Collapse toggle (desktop only) */}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="hidden md:flex items-center justify-center w-full py-1.5 rounded text-[#5c5e6a] hover:bg-[#22262e] hover:text-[#e4e4e7] transition-colors"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </button>

          {/* Status */}
          <div className={`flex items-center ${collapsed ? 'justify-center' : 'justify-between px-2'} py-1`}>
            {!collapsed && <span className="font-mono text-[10px] text-[#5c5e6a]">v2.0.0</span>}
            <div className="flex items-center gap-1.5" title="System Online">
              <span className="w-1.5 h-1.5 rounded-full bg-[#22c55e]" />
            </div>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        
        {/* Top bar */}
        <header className="h-12 bg-[#1a1d24] border-b border-[#2a2e38] flex items-center px-4 justify-between sticky top-0 z-30">
          <div className="flex items-center gap-3">
            <button 
              className="md:hidden text-[#8b8d98] hover:text-[#e4e4e7]"
              onClick={() => setMobileOpen(true)}
              aria-label="Open menu"
            >
              <Menu className="h-5 w-5" />
            </button>
            <div className="flex items-center text-xs text-[#8b8d98]">
              ScopeGuard
              <ChevronRight className="h-3 w-3 mx-1 text-[#5c5e6a]" />
              <span className="text-[#e4e4e7] font-medium">{getPageTitle()}</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
             <div className="flex items-center gap-1.5 text-xs text-[#8b8d98] bg-[#22262e] px-2 py-1 rounded border border-[#2a2e38]">
                <Activity className="h-3 w-3 text-[#22c55e]" />
                <span className="hidden sm:inline">Engine Active</span>
             </div>
          </div>
        </header>

        {/* Content area */}
        <main className="flex-1 overflow-x-hidden overflow-y-auto p-4 md:p-6 lg:p-8 bg-[#111318]">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
