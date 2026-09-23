import axios from 'axios';
import type {
  CommitAnalysis,
  CommitRiskAnalysis,
  CommitTestAnalysis,
  DependencyAnalysis,
  FullAnalysisResult,
  HistoricalAnalysisResult,
  ImpactResult,
  WhatIfResult,
  PRAnalysisResult,
} from '../types/api';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

const client = axios.create({
  baseURL: `${API_BASE}/api`,
  headers: { 'Content-Type': 'application/json' },
  timeout: 600_000,
});

export const api = {
  /* Dependency graph */
  analyzeDependencies: (path: string) =>
    client.post<DependencyAnalysis>('/analyze/dependencies', { path }).then(r => r.data),

  getComponentImpact: (componentId: string, repositoryPath: string) =>
    client.get<ImpactResult>(`/analyze/dependencies/${encodeURIComponent(componentId)}/impact`, {
      params: { repository_path: repositoryPath },
    }).then(r => r.data),

  /* Commit analysis */
  analyzeCommit: (path: string, commit: string) =>
    client.post<CommitAnalysis>('/analyze/commit', { path, commit }).then(r => r.data),

  /* Risk analysis */
  analyzeCommitRisk: (path: string, commit: string) =>
    client.post<CommitRiskAnalysis>('/analyze/commit/risk', { path, commit }).then(r => r.data),

  /* Test impact */
  analyzeCommitTests: (path: string, commit: string) =>
    client.post<CommitTestAnalysis>('/analyze/commit/tests', { path, commit }).then(r => r.data),

  /* History */
  analyzeHistory: (path: string, limit = 20) =>
    client.post<HistoricalAnalysisResult>('/analyze/history', { path, limit }).then(r => r.data),

  /* Full analysis — local repository */
  analyzeFull: (path: string) =>
    client.post<FullAnalysisResult>('/analyze/full', { path }).then(r => r.data),

  /* GitHub repository analysis */
  analyzeGitHub: (url: string) =>
    client.post<FullAnalysisResult>('/analyze/github', { url }).then(r => r.data),

  /* What-If simulation */
  analyzeWhatIf: (path: string, component_id: string) =>
    client.post<WhatIfResult>('/analyze/what-if', { path, component_id }).then(r => r.data),

  /* PR analysis */
  analyzePR: (path: string, base_commit: string, head_commit: string) =>
    client.post<PRAnalysisResult>('/analyze/pr', { path, base_commit, head_commit }).then(r => r.data),

  /* Health */
  health: () =>
    client.get<{ status: string }>('/health', { baseURL: API_BASE }).then(r => r.data),
};
