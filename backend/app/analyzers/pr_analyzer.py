"""Pull Request analysis service.

Compares two commits (base → head) and produces a comprehensive
PR risk report by reusing the existing analysis infrastructure.

The PR analyzer does NOT modify the repository.
"""

import ast
import logging
from pathlib import Path

from app.analyzers.complexity_analyzer import ComplexityAnalyzer, _ComplexityVisitor
from app.analyzers.dependency_graph import DependencyGraphBuilder, _module_name_from_path
from app.analyzers.hotspot_analyzer import HotspotAnalyzer
from app.analyzers.impact_analyzer import ImpactAnalyzer
from app.analyzers.repository_scanner import RepositoryScanner
from app.analyzers.risk_engine import RiskEngine
from app.analyzers.test_impact_analyzer import TestImpactAnalyzer
from app.analyzers.test_analyzer import TestAnalyzer
from app.models.change_models import ChangeType, CommitAnalysis
from app.models.pr_models import ComplexityDelta, PRAnalysisResult
from app.services.git_service import GitService

logger = logging.getLogger(__name__)


class PRAnalyzer:
    """Analyzes a Pull Request by comparing base and head commits.

    Reuses existing ImpactAnalyzer, RiskEngine, TestImpactAnalyzer,
    ComplexityAnalyzer, and HotspotAnalyzer.
    """

    def __init__(self) -> None:
        self._git = GitService()

    def analyze_pr(
        self,
        repo_path: Path,
        base_commit: str,
        head_commit: str,
    ) -> PRAnalysisResult:
        """Analyze a PR by comparing base and head commits."""
        repo = self._git.open_repo(repo_path)

        # Get commit info for both
        base_info = self._git.get_commit_info(repo, base_commit)
        head_info = self._git.get_commit_info(repo, head_commit)

        # Get cumulative file changes between base and head
        file_changes = self._git.get_file_changes_between(
            repo, base_commit, head_commit,
        )
        total_additions = sum(fc.additions for fc in file_changes)
        total_deletions = sum(fc.deletions for fc in file_changes)

        # 1. Impact Analysis (using new analyze_diff)
        impact_analyzer = ImpactAnalyzer()
        head_analysis = impact_analyzer.analyze_diff(repo_path, base_commit, head_commit)

        # 2. Risk Engine
        engine = RiskEngine()
        risk = engine.calculate(head_analysis)

        # 3. Test Impact Analysis
        # We manually orchestrate to reuse the graph and avoid double-impact-analysis
        try:
            scanner = RepositoryScanner()
            repo_analysis = scanner.scan(repo_path)
            graph_builder = DependencyGraphBuilder()
            graph_builder.build(repo_analysis)
            
            test_analyzer = TestAnalyzer()
            tests = test_analyzer.discover_tests(repo_path)
            mappings = test_analyzer.build_mappings(tests, repo_path, set(graph_builder.graph.nodes))
            
            test_impact = TestImpactAnalyzer()
            test_selection = test_impact._select_tests(head_analysis, tests, mappings)
        except Exception as e:
            logger.warning('Could not analyze test impact: %s', e)
            from app.models.test_models import TestSelectionResult
            test_selection = TestSelectionResult()

        # 4. Complexity Delta (Zero-checkout strategy)
        complexity_delta = self._compute_complexity_delta(
            repo_path, repo, base_commit, head_commit, head_analysis, file_changes
        )

        # 5. Hotspot Analysis
        hotspots_touched, hotspot_count = self._check_hotspots(
            repo_path, head_analysis,
        )

        return PRAnalysisResult(
            repository_path=str(repo_path),
            base_commit=base_info,
            head_commit=head_info,
            file_changes=file_changes,
            total_additions=total_additions,
            total_deletions=total_deletions,
            changed_components=head_analysis.changed_components,
            direct_impact=head_analysis.direct_impact,
            transitive_impact=head_analysis.transitive_impact,
            affected_apis=head_analysis.affected_apis,
            blast_radius=head_analysis.blast_radius,
            test_selection=test_selection,
            complexity_delta=complexity_delta,
            hotspots_touched=hotspots_touched,
            hotspot_count=hotspot_count,
            risk=risk,
        )

    def _compute_complexity_delta(
        self,
        repo_path: Path,
        repo,
        base_commit: str,
        head_commit: str,
        head_analysis: CommitAnalysis,
        file_changes: list,
    ) -> ComplexityDelta:
        """Compute complexity change between base and head without checkout."""
        try:
            # Analyze complexity at HEAD (current state)
            analyzer = ComplexityAnalyzer()
            head_complexity = analyzer.analyze_repository(repo_path)
            
            total_funcs_after = head_complexity.summary.total_functions
            sum_cc_after = head_complexity.summary.average_complexity * total_funcs_after
            
            added_funcs = 0
            removed_funcs = 0
            cc_removed = 0
            cc_added = 0
            
            # Analyze Git blobs for changed files to compute BEFORE metrics
            for fc in file_changes:
                if not fc.path.endswith('.py'):
                    continue
                
                # If deleted, all functions in it are removed
                if fc.change_type == ChangeType.DELETED:
                    old_source = self._git.get_file_at_commit(repo, base_commit, getattr(fc, 'old_path', None) or fc.path)
                    if old_source:
                        cc, count = self._sum_complexity_for_source(old_source)
                        removed_funcs += count
                        cc_removed += cc
                
                # If added, all functions in it are added
                elif fc.change_type == ChangeType.ADDED:
                    new_source = self._git.get_file_at_commit(repo, head_commit, fc.path)
                    if new_source:
                        cc, count = self._sum_complexity_for_source(new_source)
                        added_funcs += count
                        cc_added += cc
                
                # If modified or renamed, diff the functions
                else:
                    old_path = getattr(fc, 'old_path', None) or fc.path
                    old_source = self._git.get_file_at_commit(repo, base_commit, old_path)
                    new_source = self._git.get_file_at_commit(repo, head_commit, fc.path)
                    
                    if old_source and new_source:
                        old_cc, old_count = self._sum_complexity_for_source(old_source)
                        new_cc, new_count = self._sum_complexity_for_source(new_source)
                        # The net difference for this file
                        cc_removed += old_cc
                        cc_added += new_cc
                        removed_funcs += old_count
                        added_funcs += new_count

            total_funcs_before = total_funcs_after - added_funcs + removed_funcs
            sum_cc_before = sum_cc_after - cc_added + cc_removed
            avg_cc_before = (sum_cc_before / total_funcs_before) if total_funcs_before > 0 else 0.0
            avg_cc_after = head_complexity.summary.average_complexity
            
            pct_change = 0.0
            if avg_cc_before > 0:
                pct_change = ((avg_cc_after - avg_cc_before) / avg_cc_before) * 100.0

            # Find most complex changed functions
            changed_ids = {cc.component_id for cc in head_analysis.changed_components}
            most_complex_changed = [
                fc.component_id
                for fc in head_complexity.most_complex
                if fc.component_id in changed_ids
            ]

            return ComplexityDelta(
                total_functions_before=int(total_funcs_before),
                total_functions_after=total_funcs_after,
                functions_added=added_funcs,
                functions_removed=removed_funcs,
                average_complexity_before=round(avg_cc_before, 2),
                average_complexity_after=avg_cc_after,
                complexity_change_percentage=round(pct_change, 2),
                most_complex_changed=most_complex_changed[:10],
            )
        except Exception as e:
            logger.warning('Could not compute complexity delta: %s', e)
            return ComplexityDelta()

    def _sum_complexity_for_source(self, source: str) -> tuple[int, int]:
        """Parse source and return (total_cyclomatic_complexity, function_count)."""
        try:
            tree = ast.parse(source)
            total_cc = 0
            count = 0
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    visitor = _ComplexityVisitor()
                    for child in node.body:
                        visitor.visit(child)
                    total_cc += visitor.complexity
                    count += 1
            return total_cc, count
        except (SyntaxError, Exception):
            return 0, 0

    def _check_hotspots(
        self,
        repo_path: Path,
        head_analysis: CommitAnalysis,
    ) -> tuple[list[str], int]:
        """Check if any changed components are engineering hotspots."""
        try:
            hotspot_analyzer = HotspotAnalyzer()
            hotspot_result = hotspot_analyzer.analyze_hotspots(repo_path)

            changed_ids = {cc.component_id for cc in head_analysis.changed_components}
            hotspot_ids = {
                h.component_id
                for h in hotspot_result.hotspots
                if h.hotspot_score >= 40.0
            }

            touched = sorted(changed_ids & hotspot_ids)
            return touched, len(touched)
        except Exception as e:
            logger.warning('Could not check hotspots: %s', e)
            return [], 0
