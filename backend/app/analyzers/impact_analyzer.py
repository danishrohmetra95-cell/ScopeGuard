"""Impact analyzer for Git commit changes.

Orchestrates the complete commit analysis pipeline:

    Git Diff
        |
    Changed Files
        |
    AST Comparison  ->  Changed Components
        |
    Dependency Graph (built from current HEAD)
        |
    Direct Impact
        |
    Transitive Impact
        |
    Blast Radius

Architectural decision:
    The dependency graph is built from the CURRENT state of the repository
    (HEAD), not from the commit being analyzed. This means the impact
    analysis answers: "given the current dependency structure, what would
    be affected if these components changed?"  This is the correct
    behaviour for regression risk assessment.
"""

import logging
from pathlib import Path

from app.analyzers.change_detector import ChangeDetector
from app.analyzers.dependency_graph import DependencyGraphBuilder, _module_name_from_path
from app.analyzers.repository_scanner import RepositoryScanner
from app.models.analysis_models import RepositoryAnalysis
from app.models.change_models import (
    AffectedAPI,
    BlastRadius,
    CommitAnalysis,
    ComponentChange,
    ImpactedComponent,
)
from app.models.graph_models import ComponentType
from app.services.git_service import GitService

logger = logging.getLogger(__name__)


class ImpactAnalyzer:
    """Analyzes the impact of a Git commit on the codebase.

    Pipeline:
        1. Extract commit metadata and file changes  (GitService)
        2. Detect function-level changes              (ChangeDetector)
        3. Build dependency graph from current HEAD    (DependencyGraphBuilder)
        4. Map changes to graph nodes
        5. Traverse graph for direct / transitive dependents
        6. Identify affected API routes
        7. Compute blast radius summary
    """

    def __init__(self) -> None:
        self._git = GitService()
        self._detector = ChangeDetector()
        self._scanner = RepositoryScanner()

    def analyze_commit(
        self, repo_path: Path, commit_hash: str,
    ) -> CommitAnalysis:
        """Run the full impact analysis pipeline for a commit.

        Args:
            repo_path: Path to the Git repository.
            commit_hash: Commit hash to analyze.

        Returns:
            CommitAnalysis with full impact assessment.
        """
        logger.info('Analyzing commit %s in %s', commit_hash, repo_path)

        # 1. Open repo, get commit info and file changes
        repo = self._git.open_repo(repo_path)
        commit_info = self._git.get_commit_info(repo, commit_hash)
        file_changes = self._git.get_file_changes(repo, commit_hash)

        # 2. Detect component-level changes
        changed_components = self._detector.detect_changes(
            repo, commit_hash, file_changes,
        )

        # 3. Build dependency graph from current HEAD
        repo_analysis = self._scanner.scan(repo_path)
        graph_builder = DependencyGraphBuilder()
        graph_builder.build(repo_analysis)

        # 4-5. Compute impact
        direct_impact, transitive_impact = self._compute_impact(
            changed_components, graph_builder,
        )

        # 6. Find affected APIs
        affected_apis = self._find_affected_apis(
            changed_components, direct_impact, transitive_impact,
            repo_analysis,
        )

        # 7. Compute blast radius
        blast_radius = self._compute_blast_radius(
            file_changes, changed_components,
            direct_impact, transitive_impact, affected_apis,
        )

        return CommitAnalysis(
            repository_path=str(repo_path),
            commit=commit_info,
            file_changes=file_changes,
            changed_components=changed_components,
            direct_impact=direct_impact,
            transitive_impact=transitive_impact,
            affected_apis=affected_apis,
            blast_radius=blast_radius,
        )

    def analyze_diff(
        self, repo_path: Path, base_commit: str, head_commit: str,
    ) -> CommitAnalysis:
        """Run the full impact analysis pipeline for a commit range (PR).

        Args:
            repo_path: Path to the Git repository.
            base_commit: Base commit hash.
            head_commit: Head commit hash.

        Returns:
            CommitAnalysis with full impact assessment.
        """
        logger.info('Analyzing diff %s..%s in %s', base_commit, head_commit, repo_path)

        # 1. Open repo, get commit info and file changes
        repo = self._git.open_repo(repo_path)
        commit_info = self._git.get_commit_info(repo, head_commit)
        file_changes = self._git.get_file_changes_between(repo, base_commit, head_commit)

        # 2. Detect component-level changes using base_commit
        changed_components = self._detector.detect_changes(
            repo, head_commit, file_changes, base_hash=base_commit,
        )

        # 3. Build dependency graph from current HEAD
        repo_analysis = self._scanner.scan(repo_path)
        graph_builder = DependencyGraphBuilder()
        graph_builder.build(repo_analysis)

        # 4-5. Compute impact
        direct_impact, transitive_impact = self._compute_impact(
            changed_components, graph_builder,
        )

        # 6. Find affected APIs
        affected_apis = self._find_affected_apis(
            changed_components, direct_impact, transitive_impact,
            repo_analysis,
        )

        # 7. Compute blast radius
        blast_radius = self._compute_blast_radius(
            file_changes, changed_components,
            direct_impact, transitive_impact, affected_apis,
        )

        return CommitAnalysis(
            repository_path=str(repo_path),
            commit=commit_info,
            file_changes=file_changes,
            changed_components=changed_components,
            direct_impact=direct_impact,
            transitive_impact=transitive_impact,
            affected_apis=affected_apis,
            blast_radius=blast_radius,
        )

    # ------------------------------------------------------------------
    # Impact computation
    # ------------------------------------------------------------------

    def _compute_impact(
        self,
        changed_components: list[ComponentChange],
        graph_builder: DependencyGraphBuilder,
    ) -> tuple[list[ImpactedComponent], list[ImpactedComponent]]:
        """Compute direct and transitive impact for changed components."""
        changed_ids = {cc.component_id for cc in changed_components}
        seen_direct: dict[str, ImpactedComponent] = {}
        seen_transitive: dict[str, ImpactedComponent] = {}

        for cc in changed_components:
            cid = cc.component_id
            if cid not in graph_builder.graph:
                continue

            # Direct dependents
            try:
                direct_deps = graph_builder.get_direct_dependents(cid)
            except KeyError:
                continue

            for dep_id in direct_deps:
                if dep_id in changed_ids:
                    continue
                if dep_id in seen_direct:
                    if cid not in seen_direct[dep_id].source_changes:
                        seen_direct[dep_id].source_changes.append(cid)
                else:
                    attrs = graph_builder.graph.nodes.get(dep_id, {})
                    seen_direct[dep_id] = ImpactedComponent(
                        component_id=dep_id,
                        component_type=ComponentType(
                            attrs.get('component_type', 'module'),
                        ),
                        impact_type='direct',
                        source_changes=[cid],
                    )

            # Transitive dependents
            try:
                transitive_deps = graph_builder.get_transitive_dependents(cid)
            except KeyError:
                continue

            for dep_id in transitive_deps:
                if dep_id in changed_ids or dep_id in seen_direct:
                    continue
                if dep_id in seen_transitive:
                    if cid not in seen_transitive[dep_id].source_changes:
                        seen_transitive[dep_id].source_changes.append(cid)
                else:
                    attrs = graph_builder.graph.nodes.get(dep_id, {})
                    seen_transitive[dep_id] = ImpactedComponent(
                        component_id=dep_id,
                        component_type=ComponentType(
                            attrs.get('component_type', 'module'),
                        ),
                        impact_type='transitive',
                        source_changes=[cid],
                    )

        direct = sorted(seen_direct.values(), key=lambda x: x.component_id)
        transitive = sorted(
            seen_transitive.values(), key=lambda x: x.component_id,
        )
        return direct, transitive

    # ------------------------------------------------------------------
    # Affected APIs
    # ------------------------------------------------------------------

    def _find_affected_apis(
        self,
        changed_components: list[ComponentChange],
        direct_impact: list[ImpactedComponent],
        transitive_impact: list[ImpactedComponent],
        repo_analysis: RepositoryAnalysis,
    ) -> list[AffectedAPI]:
        """Identify API routes affected by changes."""
        affected_ids: dict[str, str] = {}
        for cc in changed_components:
            affected_ids[cc.component_id] = 'direct'
        for imp in direct_impact:
            affected_ids[imp.component_id] = 'direct'
        for imp in transitive_impact:
            if imp.component_id not in affected_ids:
                affected_ids[imp.component_id] = 'transitive'

        apis: list[AffectedAPI] = []
        for fa in repo_analysis.files:
            if not fa.routes:
                continue
            module_name = _module_name_from_path(fa.file_path)
            module_id = f'module:{module_name}'

            for route in fa.routes:
                func_id = f'function:{module_name}.{route.function_name}'
                impact = affected_ids.get(
                    func_id,
                    affected_ids.get(module_id),
                )
                if impact:
                    apis.append(AffectedAPI(
                        route_path=route.path,
                        http_method=route.http_method,
                        function_name=route.function_name,
                        file_path=fa.file_path,
                        impact_type=impact,
                    ))

        return apis

    # ------------------------------------------------------------------
    # Blast radius
    # ------------------------------------------------------------------

    def _compute_blast_radius(
        self,
        file_changes,
        changed_components: list[ComponentChange],
        direct_impact: list[ImpactedComponent],
        transitive_impact: list[ImpactedComponent],
        affected_apis: list[AffectedAPI],
    ) -> BlastRadius:
        """Compute summary blast radius statistics."""
        all_affected: set[str] = set()
        for cc in changed_components:
            all_affected.add(cc.component_id)
        for imp in direct_impact:
            all_affected.add(imp.component_id)
        for imp in transitive_impact:
            all_affected.add(imp.component_id)

        all_impacted = list(direct_impact) + list(transitive_impact)

        return BlastRadius(
            changed_file_count=len(file_changes),
            changed_component_count=len(changed_components),
            direct_impact_count=len(direct_impact),
            transitive_impact_count=len(transitive_impact),
            total_affected_count=len(all_affected),
            affected_module_count=sum(
                1 for i in all_impacted
                if i.component_type == ComponentType.MODULE
            ),
            affected_function_count=sum(
                1 for i in all_impacted
                if i.component_type == ComponentType.FUNCTION
            ),
            affected_class_count=sum(
                1 for i in all_impacted
                if i.component_type == ComponentType.CLASS
            ),
            affected_method_count=sum(
                1 for i in all_impacted
                if i.component_type == ComponentType.METHOD
            ),
            affected_api_count=len(affected_apis),
        )
