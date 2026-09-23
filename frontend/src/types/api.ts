// TypeScript types matching actual FastAPI backend Pydantic models

// ---- Graph / Dependency Models ----

export type ComponentType = 'module' | 'class' | 'function' | 'method';
export type DependencyType = 'imports' | 'calls' | 'contains';

export interface ComponentNode {
  component_id: string;
  component_type: ComponentType;
  name: string;
  file_path: string | null;
  line_number: number | null;
  classification?: string;
  metadata: Record<string, string | number | boolean | null>;
}

export interface DependencyEdge {
  source: string;
  target: string;
  dependency_type: DependencyType;
  metadata: Record<string, string | number | boolean | null>;
}

export interface UnresolvedDependency {
  source: string;
  raw_name: string;
  dependency_type: DependencyType;
  reason: string;
  file_path: string | null;
  line_number: number | null;
}

export interface HighConnectivityComponent {
  component_id: string;
  component_type: ComponentType;
  in_degree: number;
  out_degree: number;
  total_degree: number;
}

export interface GraphStatistics {
  total_nodes: number;
  total_edges: number;
  module_count: number;
  class_count: number;
  function_count: number;
  method_count: number;
  import_edges: number;
  call_edges: number;
  contains_edges: number;
  unresolved_count: number;
  connected_components: number;
  highest_in_degree: HighConnectivityComponent[];
  highest_out_degree: HighConnectivityComponent[];
}

export interface DependencyAnalysis {
  repository_path: string;
  statistics: GraphStatistics;
  nodes: ComponentNode[];
  edges: DependencyEdge[];
  unresolved: UnresolvedDependency[];
  high_connectivity: HighConnectivityComponent[];
}

export interface ImpactResult {
  component_id: string;
  direct_dependents: string[];
  transitive_dependents: string[];
  direct_count: number;
  transitive_count: number;
}

// ---- Change / Commit Models ----

export interface CommitInfo {
  commit_hash: string;
  short_hash: string;
  author: string;
  author_email?: string;
  message: string;
  timestamp: string;
  parent_hash: string | null;
  changed_file_count: number;
}

export interface FileChange {
  path: string;
  change_type: 'added' | 'deleted' | 'modified' | 'renamed';
  old_path?: string | null;
  additions: number;
  deletions: number;
}

export interface ComponentChange {
  component_id: string;
  component_type: string;
  change_type: 'added' | 'removed' | 'modified';
  file_path: string;
  name: string;
  change_semantics?: string | null;
}

export interface ImpactedComponent {
  component_id: string;
  impact_type: 'direct' | 'transitive';
  source_changes: string[];
}

export interface AffectedAPI {
  route_path: string | null;
  http_method: string;
  function_name: string;
  file_path: string;
  impact_type: string;
}

export interface BlastRadius {
  changed_file_count: number;
  changed_component_count: number;
  direct_impact_count: number;
  transitive_impact_count: number;
  total_affected_count: number;
  affected_api_count: number;
}

export interface CommitAnalysis {
  repository_path: string;
  commit: CommitInfo;
  file_changes: FileChange[];
  changed_components: ComponentChange[];
  direct_impact: ImpactedComponent[];
  transitive_impact: ImpactedComponent[];
  affected_apis: ImpactedComponent[];
  blast_radius: BlastRadius;
}

// ---- Risk Models ----

export interface RiskFactor {
  name: string;
  description: string;
  points: number;
  severity: 'info' | 'warning' | 'critical';
}

export interface RiskScore {
  score: number;
  level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  factors: RiskFactor[];
  summary: string;
  recommendations: string[];
}

export interface CommitRiskAnalysis extends CommitAnalysis {
  risk: RiskScore;
}

// ---- Test Models ----

export interface TestCase {
  test_id: string;
  test_name: string;
  module_name: string;
  file_path?: string;
}

export interface TestSelection {
  test: TestCase;
  priority: 'HIGH' | 'MEDIUM' | 'LOW';
  reason: string;
  affected_components: string[];
}

export interface TestSelectionResult {
  total_tests: number;
  selected_tests: number;
  skipped_tests: number;
  selection_percentage: number;
  high_priority: TestSelection[];
  medium_priority: TestSelection[];
  low_priority: TestSelection[];
}

export interface CommitTestAnalysis extends CommitAnalysis {
  test_selection: TestSelectionResult;
}

// ---- Historical Models ----

export interface HistoricalCommit {
  commit_hash: string;
  short_hash: string;
  author: string;
  message: string;
  timestamp: string;
  changed_file_count: number;
  changed_component_count: number;
  direct_impact_count: number;
  transitive_impact_count: number;
  affected_api_count: number;
  risk_score: number;
  risk_level: string;
  selected_test_count: number;
}

export interface ComponentHistory {
  component_id: string;
  change_count: number;
  modification_count: number;
  addition_count: number;
  removal_count: number;
  average_risk: number;
  max_risk: number;
  total_direct_impact: number;
  total_transitive_impact: number;
  hotspot_score: number;
}

export interface FrequentlyAffectedComponent {
  component_id: string;
  times_affected: number;
  source_components: string[];
}

export interface RiskTrendPoint {
  commit_hash: string;
  timestamp: string;
  score: number;
  risk_level: string;
}

export interface RiskTrendSummary {
  average_risk: number;
  highest_risk: number;
  lowest_risk: number;
  low_count: number;
  medium_count: number;
  high_count: number;
  critical_count: number;
}

export interface HistoricalAnalysisResult {
  repository_path: string;
  graph_basis?: string;
  commits_analyzed: HistoricalCommit[];
  commit_count: number;
  component_hotspots: ComponentHistory[];
  risk_trend: RiskTrendPoint[];
  risk_trend_summary: RiskTrendSummary;
  high_risk_commits: HistoricalCommit[];
  frequently_changed_components: ComponentHistory[];
  frequently_affected_components: FrequentlyAffectedComponent[];
  summary: string;
  insights: string[];
}

// ---- Repository Analysis ----

export interface RepositorySummary {
  total_files: number;
  total_lines: number;
  total_functions: number;
  total_classes: number;
  total_imports: number;
  total_calls: number;
  total_routes: number;
  files_with_errors: number;
}

export interface RepositoryAnalysis {
  repository_path: string;
  files: { file_path: string; line_count: number; functions: { name: string }[]; classes: { name: string }[] }[];
  summary: RepositorySummary;
  warnings: { file_path: string; message: string; warning_type: string }[];
  excluded_directories: string[];
}

// ---- Full Analysis Result (combined pipeline) ----

export interface FullAnalysisResult {
  risk: CommitRiskAnalysis;
  tests: CommitTestAnalysis;
  history: HistoricalAnalysisResult;
}

// ---- What-If Models ----

export interface WhatIfAffectedAPI {
  route_path: string | null;
  http_method: string;
  function_name: string;
  file_path: string;
  impact_type: string;
}

export interface WhatIfAffectedTest {
  test_id: string;
  test_name: string;
  test_file: string;
  priority: string;
  reason: string;
}

export interface WhatIfBlastRadius {
  direct_impact_count: number;
  transitive_impact_count: number;
  total_affected_count: number;
  affected_api_count: number;
  affected_test_count: number;
}

export interface WhatIfResult {
  simulation: boolean;
  repository_path: string;
  component_id: string;
  component_type: string;
  component_name: string;
  file_path: string | null;
  direct_impact: string[];
  transitive_impact: string[];
  affected_apis: WhatIfAffectedAPI[];
  affected_tests: WhatIfAffectedTest[];
  blast_radius: WhatIfBlastRadius;
  predicted_risk_score: number;
  predicted_risk_level: string;
  risk_contributors: Record<string, unknown>[];
  recommendations: string[];
  complexity: Record<string, unknown> | null;
  hotspot: Record<string, unknown> | null;
  disclaimer: string;
}

// ---- PR Analysis Models ----

export interface ComplexityDelta {
  total_functions_before: number;
  total_functions_after: number;
  functions_added: number;
  functions_removed: number;
  average_complexity_before: number;
  average_complexity_after: number;
  complexity_change_percentage: number;
  most_complex_changed: string[];
}

export interface PRAffectedAPI {
  route_path: string | null;
  http_method: string;
  function_name: string;
  file_path: string;
  impact_type: string;
}

export interface PRAnalysisResult {
  repository_path: string;
  base_commit: CommitInfo;
  head_commit: CommitInfo;
  file_changes: FileChange[];
  total_additions: number;
  total_deletions: number;
  changed_components: ComponentChange[];
  direct_impact: ImpactedComponent[];
  transitive_impact: ImpactedComponent[];
  affected_apis: PRAffectedAPI[];
  blast_radius: BlastRadius;
  test_selection: TestSelectionResult;
  complexity_delta: ComplexityDelta;
  hotspots_touched: string[];
  hotspot_count: number;
  risk: RiskScore;
}
