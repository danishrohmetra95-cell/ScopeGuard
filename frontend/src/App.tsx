import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import AppLayout from './layouts/AppLayout';
import DashboardPage from './pages/DashboardPage';
import CommitAnalysisPage from './pages/CommitAnalysisPage';
import DependencyGraphPage from './pages/DependencyGraphPage';
import TestImpactPage from './pages/TestImpactPage';
import HistoryPage from './pages/HistoryPage';
import WhatIfPage from './pages/WhatIfPage';
import PRAnalysisPage from './pages/PRAnalysisPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="commit" element={<CommitAnalysisPage />} />
          <Route path="graph" element={<DependencyGraphPage />} />
          <Route path="tests" element={<TestImpactPage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="whatif" element={<WhatIfPage />} />
          <Route path="pr" element={<PRAnalysisPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
