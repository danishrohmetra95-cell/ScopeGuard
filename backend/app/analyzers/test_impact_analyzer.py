"""Test impact analyzer — determines which tests to run after a change.

Given changed components, the dependency graph, and discovered tests,
this module identifies which tests are affected and assigns priorities.

Pipeline:
    Changed Components  →  Affected Components  →  Test Mappings
                                                        ↓
                                                   Test Selection
                                                        ↓
                                                 HIGH / MEDIUM / LOW

Priority rules:
    HIGH   — test directly imports/calls a changed component
    MEDIUM — test imports/calls a component that depends on the change
    LOW    — test imports a module that is transitively affected

SAFETY: This module NEVER executes tests. It only selects them.
"""

import logging
from pathlib import Path

from app.analyzers.dependency_graph import DependencyGraphBuilder
from app.analyzers.impact_analyzer import ImpactAnalyzer
from app.analyzers.repository_scanner import RepositoryScanner
from app.analyzers.test_analyzer import TestAnalyzer
from app.models.change_models import CommitAnalysis
from app.models.test_models import (
    CommitTestAnalysis,
    TestCase,
    TestImpact,
    TestMapping,
    TestPriority,
    TestSelectionResult,
)

logger = logging.getLogger(__name__)


class TestImpactAnalyzer:
    """Determines which tests are affected by a code change."""

    def __init__(self) -> None:
        self._impact_analyzer = ImpactAnalyzer()
        self._test_analyzer = TestAnalyzer()
        self._scanner = RepositoryScanner()

    def analyze_commit_tests(
        self, repo_path: Path, commit_hash: str,
    ) -> CommitTestAnalysis:
        """Run the full test impact analysis pipeline.

        Args:
            repo_path: Path to the Git repository.
            commit_hash: Commit to analyze.

        Returns:
            CommitTestAnalysis with M3 analysis plus test selection.
        """
        # 1. Run M3 commit analysis
        analysis = self._impact_analyzer.analyze_commit(repo_path, commit_hash)

        # 2. Build dependency graph (needed for mapping)
        repo_analysis = self._scanner.scan(repo_path)
        graph_builder = DependencyGraphBuilder()
        graph_builder.build(repo_analysis)
        graph_node_ids = set(graph_builder.graph.nodes)

        # 3. Discover tests
        tests = self._test_analyzer.discover_tests(repo_path)

        # 4. Build test-to-component mappings
        mappings = self._test_analyzer.build_mappings(
            tests, repo_path, graph_node_ids,
        )

        # 5. Calculate test selection
        selection = self._select_tests(analysis, tests, mappings)

        return CommitTestAnalysis(
            repository_path=analysis.repository_path,
            commit=analysis.commit,
            file_changes=analysis.file_changes,
            changed_components=analysis.changed_components,
            direct_impact=analysis.direct_impact,
            transitive_impact=analysis.transitive_impact,
            blast_radius=analysis.blast_radius,
            test_selection=selection,
        )

    def analyze_diff_tests(
        self, repo_path: Path, base_commit: str, head_commit: str,
    ) -> CommitTestAnalysis:
        """Run the full test impact analysis pipeline for a PR commit range.

        Args:
            repo_path: Path to the Git repository.
            base_commit: Base commit hash.
            head_commit: Head commit hash.

        Returns:
            CommitTestAnalysis with M3 analysis plus test selection.
        """
        # 1. Run M3 commit analysis for the diff
        analysis = self._impact_analyzer.analyze_diff(repo_path, base_commit, head_commit)

        # 2. Build dependency graph (needed for mapping)
        repo_analysis = self._scanner.scan(repo_path)
        graph_builder = DependencyGraphBuilder()
        graph_builder.build(repo_analysis)
        graph_node_ids = set(graph_builder.graph.nodes)

        # 3. Discover tests
        tests = self._test_analyzer.discover_tests(repo_path)

        # 4. Build test-to-component mappings
        mappings = self._test_analyzer.build_mappings(
            tests, repo_path, graph_node_ids,
        )

        # 5. Calculate test selection
        selection = self._select_tests(analysis, tests, mappings)

        return CommitTestAnalysis(
            repository_path=analysis.repository_path,
            commit=analysis.commit,
            file_changes=analysis.file_changes,
            changed_components=analysis.changed_components,
            direct_impact=analysis.direct_impact,
            transitive_impact=analysis.transitive_impact,
            blast_radius=analysis.blast_radius,
            test_selection=selection,
        )

    def _select_tests(
        self,
        analysis: CommitAnalysis,
        tests: list[TestCase],
        mappings: list[TestMapping],
    ) -> TestSelectionResult:
        """Select and prioritise tests based on impact analysis."""
        changed_ids = {cc.component_id for cc in analysis.changed_components}
        direct_ids = {imp.component_id for imp in analysis.direct_impact}
        transitive_ids = {imp.component_id for imp in analysis.transitive_impact}

        # Also build module-level sets for broader matching
        changed_modules = {
            cid for cid in changed_ids if cid.startswith('module:')
        }
        for cc in analysis.changed_components:
            mod_name = cc.component_id.split(':')[1].split('.')[0]
            changed_modules.add(f'module:{mod_name}')

        direct_modules = {
            cid for cid in direct_ids if cid.startswith('module:')
        }
        transitive_modules = {
            cid for cid in transitive_ids if cid.startswith('module:')
        }

        # Map test_id -> mapping
        mapping_by_id = {m.test_id: m for m in mappings}

        high: list[TestImpact] = []
        medium: list[TestImpact] = []
        low: list[TestImpact] = []
        selected_ids: set[str] = set()

        for test in tests:
            mapping = mapping_by_id.get(test.test_id)
            if not mapping:
                continue

            ref_ids = set(mapping.referenced_component_ids)
            ref_mods = {f'module:{m}' for m in mapping.referenced_modules}

            # HIGH: test directly references a changed component
            direct_refs = ref_ids & changed_ids
            direct_mod_refs = ref_mods & changed_modules
            if direct_refs or direct_mod_refs:
                matched = direct_refs | direct_mod_refs
                reason = (
                    f'Test directly references changed component: '
                    f'{", ".join(sorted(matched))}'
                )
                chain = f'{test.test_id} → {", ".join(sorted(matched))}'
                high.append(TestImpact(
                    test=test,
                    priority=TestPriority.HIGH,
                    reason=reason,
                    affected_components=sorted(matched),
                    impact_chain=chain,
                ))
                selected_ids.add(test.test_id)
                continue

            # MEDIUM: test references a directly impacted component
            impact_refs = ref_ids & direct_ids
            impact_mod_refs = ref_mods & direct_modules
            if impact_refs or impact_mod_refs:
                matched = impact_refs | impact_mod_refs
                reason = (
                    f'Test depends on directly affected component: '
                    f'{", ".join(sorted(matched))}'
                )
                chain = f'{test.test_id} → {", ".join(sorted(matched))} → change'
                medium.append(TestImpact(
                    test=test,
                    priority=TestPriority.MEDIUM,
                    reason=reason,
                    affected_components=sorted(matched),
                    impact_chain=chain,
                ))
                selected_ids.add(test.test_id)
                continue

            # LOW: test references a transitively impacted component
            trans_refs = ref_ids & transitive_ids
            trans_mod_refs = ref_mods & transitive_modules
            if trans_refs or trans_mod_refs:
                matched = trans_refs | trans_mod_refs
                reason = (
                    f'Test depends on transitively affected component: '
                    f'{", ".join(sorted(matched))}'
                )
                chain = (
                    f'{test.test_id} → {", ".join(sorted(matched))} '
                    f'→ ... → change'
                )
                low.append(TestImpact(
                    test=test,
                    priority=TestPriority.LOW,
                    reason=reason,
                    affected_components=sorted(matched),
                    impact_chain=chain,
                ))
                selected_ids.add(test.test_id)

        total = len(tests)
        selected = len(selected_ids)
        skipped = total - selected
        pct = (selected / total * 100.0) if total > 0 else 0.0

        return TestSelectionResult(
            total_tests=total,
            selected_tests=selected,
            skipped_tests=skipped,
            selection_percentage=round(pct, 1),
            high_priority=high,
            medium_priority=medium,
            low_priority=low,
        )
