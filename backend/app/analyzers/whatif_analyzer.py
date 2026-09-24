"""What-If impact simulator.

Predicts the impact of a hypothetical change to a component by reusing
the existing dependency graph, test analyzer, and risk engine.

This is a READ-ONLY simulation — no repository code is modified or executed.
"""

import logging
from pathlib import Path

from app.analyzers.dependency_graph import DependencyGraphBuilder
from app.analyzers.repository_scanner import RepositoryScanner
from app.analyzers.risk_engine import RiskEngine
from app.analyzers.test_analyzer import TestAnalyzer
from app.models.analysis_models import RepositoryAnalysis
from app.models.change_models import (
    BlastRadius,
    CommitAnalysis,
    CommitInfo,
    ComponentChange,
    ComponentChangeType,
)
from app.models.graph_models import ComponentType
from app.models.whatif_models import (
    WhatIfAffectedAPI,
    WhatIfAffectedTest,
    WhatIfBlastRadius,
    WhatIfResult,
)

logger = logging.getLogger(__name__)


class WhatIfAnalyzer:
    """Simulates the impact of changing a component.

    Reuses the existing dependency graph, test analyzer, and risk engine.
    All results are clearly labeled as simulation/prediction.
    """

    def simulate(self, repo_path: Path, component_id: str) -> WhatIfResult:
        """Simulate what happens if a component changes.

        Args:
            repo_path: Path to the repository.
            component_id: Component ID to simulate a change for.

        Returns:
            WhatIfResult with predicted impact, affected tests, and risk.

        Raises:
            FileNotFoundError: If repo_path does not exist.
            NotADirectoryError: If repo_path is not a directory.
            KeyError: If component_id is not found in the dependency graph.
        """
        # Step 1: Scan repository
        scanner = RepositoryScanner()
        repo_analysis = scanner.scan(repo_path)

        # Step 2: Build dependency graph
        graph_builder = DependencyGraphBuilder()
        dep_analysis = graph_builder.build(repo_analysis)

        # Step 3: Verify component exists
        if component_id not in graph_builder.graph:
            raise KeyError(f'Component not found in dependency graph: {component_id}')

        # Get component info
        node_data = graph_builder.graph.nodes[component_id]
        component_type = node_data.get('component_type', 'unknown')
        component_name = node_data.get('name', '')
        file_path = node_data.get('file_path')

        # Step 4: Get impact from dependency graph
        impact = graph_builder.get_impact(component_id)
        direct_impact = impact.direct_dependents
        transitive_impact = impact.transitive_dependents

        # Step 5: Find affected APIs
        affected_apis = self._find_affected_apis(
            repo_analysis, component_id, direct_impact, transitive_impact,
        )

        # Step 6: Find affected tests
        affected_tests = self._find_affected_tests(
            repo_path, repo_analysis, graph_builder,
            component_id, direct_impact, transitive_impact,
        )

        # Step 7: Calculate blast radius
        all_affected = set(direct_impact) | set(transitive_impact)
        blast_radius = WhatIfBlastRadius(
            direct_impact_count=len(direct_impact),
            transitive_impact_count=len(transitive_impact),
            total_affected_count=len(all_affected),
            affected_api_count=len(affected_apis),
            affected_test_count=len(affected_tests),
        )

        # Step 8: Predict risk score using the existing risk engine
        risk_result = self._predict_risk(
            component_id, component_type, direct_impact,
            transitive_impact, affected_apis,
        )

        # Step 9: Phase 2 Integration (Complexity and Hotspots)
        complexity_data = None
        hotspot_data = None
        try:
            from app.analyzers.complexity_analyzer import ComplexityAnalyzer
            from app.analyzers.hotspot_analyzer import HotspotAnalyzer
            
            c_analyzer = ComplexityAnalyzer()
            c_result = c_analyzer.analyze_repository(repo_path, repo_analysis, graph_builder)
            
            for fc in c_result.functions:
                if fc.component_id == component_id:
                    complexity_data = {
                        'cyclomatic_complexity': fc.cyclomatic_complexity,
                        'lines_of_code': fc.lines_of_code,
                        'max_nesting_depth': fc.max_nesting_depth,
                        'branch_count': fc.branch_count,
                        'loop_count': fc.loop_count,
                        'parameter_count': fc.parameter_count,
                    }
                    break
            
            h_analyzer = HotspotAnalyzer()
            h_result = h_analyzer.analyze_hotspots(repo_path, repo_analysis)
            
            for hc in h_result.hotspots:
                if hc.component_id == component_id:
                    hotspot_data = {
                        'hotspot_score': hc.hotspot_score,
                        'complexity_score': hc.complexity_score,
                        'dependency_score': hc.dependency_score,
                        'impact_score': hc.impact_score,
                        'reasons': [r.description for r in hc.reasons],
                    }
                    break
        except Exception as e:
            logger.warning('Could not integrate Phase 2 data into What-If: %s', e)

        return WhatIfResult(
            repository_path=str(repo_path),
            component_id=component_id,
            component_type=component_type,
            component_name=component_name,
            file_path=file_path,
            direct_impact=direct_impact,
            transitive_impact=transitive_impact,
            affected_apis=affected_apis,
            affected_tests=affected_tests,
            blast_radius=blast_radius,
            predicted_risk_score=risk_result.score,
            predicted_risk_level=risk_result.level.value,
            risk_contributors=[
                {
                    'name': f.name, 
                    'points': f.points, 
                    'description': f.description
                } for f in risk_result.factors
            ],
            recommendations=risk_result.recommendations,
            complexity=complexity_data,
            hotspot=hotspot_data,
        )

    def get_components(self, repo_path: Path) -> list[dict]:
        """Get all components in a repository for the search dropdown.

        Returns a list of dicts with component_id, component_type, name, file_path.
        """
        scanner = RepositoryScanner()
        repo_analysis = scanner.scan(repo_path)
        graph_builder = DependencyGraphBuilder()
        dep_analysis = graph_builder.build(repo_analysis)

        components = []
        for node in dep_analysis.nodes:
            components.append({
                'component_id': node.component_id,
                'component_type': node.component_type.value,
                'name': node.name,
                'file_path': node.file_path,
            })
        return components

    def _find_affected_apis(
        self,
        repo_analysis: RepositoryAnalysis,
        component_id: str,
        direct_impact: list[str],
        transitive_impact: list[str],
    ) -> list[WhatIfAffectedAPI]:
        """Find API routes that would be affected by the simulated change."""
        affected_set = {component_id} | set(direct_impact) | set(transitive_impact)
        apis: list[WhatIfAffectedAPI] = []

        for file_analysis in repo_analysis.files:
            if file_analysis.has_syntax_error:
                continue
            for route in file_analysis.routes:
                # Check if the route's handler function is in the affected set
                from pathlib import PurePosixPath
                p = PurePosixPath(file_analysis.file_path)
                if p.stem == '__init__':
                    parts = list(p.parent.parts)
                    mod_name = '.'.join(parts) if parts else '__init__'
                else:
                    parts = list(p.parent.parts) + [p.stem]
                    mod_name = '.'.join(parts)

                func_id = f'function:{mod_name}.{route.function_name}'
                module_id = f'module:{mod_name}'

                if func_id in affected_set or module_id in affected_set:
                    apis.append(WhatIfAffectedAPI(
                        route_path=route.path,
                        http_method=route.http_method,
                        function_name=route.function_name,
                        file_path=file_analysis.file_path,
                    ))

        return apis

    def _find_affected_tests(
        self,
        repo_path: Path,
        repo_analysis: RepositoryAnalysis,
        graph_builder: DependencyGraphBuilder,
        component_id: str,
        direct_impact: list[str],
        transitive_impact: list[str],
    ) -> list[WhatIfAffectedTest]:
        """Find tests that would need to be run."""
        test_analyzer = TestAnalyzer()
        tests = test_analyzer.discover_tests(repo_path)
        mappings = test_analyzer.build_mappings(tests, repo_path, set(graph_builder.graph.nodes.keys()))

        affected_set = {component_id} | set(direct_impact) | set(transitive_impact)
        affected_tests: list[WhatIfAffectedTest] = []
        seen_test_ids: set[str] = set()

        for mapping in mappings:
            for ref_id in mapping.referenced_component_ids:
                if ref_id in affected_set and mapping.test_id not in seen_test_ids:
                    seen_test_ids.add(mapping.test_id)
                    # Find the test case
                    test_case = None
                    for tc in tests:
                        if tc.test_id == mapping.test_id:
                            test_case = tc
                            break

                    if test_case:
                        # Determine priority based on proximity
                        if ref_id == component_id or ref_id in direct_impact:
                            priority = 'HIGH'
                            reason = f'Directly references affected component {ref_id}'
                        else:
                            priority = 'MEDIUM'
                            reason = f'Transitively affected via {ref_id}'

                        affected_tests.append(WhatIfAffectedTest(
                            test_id=test_case.test_id,
                            test_name=test_case.test_name,
                            test_file=test_case.test_file,
                            priority=priority,
                            reason=reason,
                        ))

        return affected_tests

    def _predict_risk(
        self,
        component_id: str,
        component_type: str,
        direct_impact: list[str],
        transitive_impact: list[str],
        affected_apis: list[WhatIfAffectedAPI],
    ) -> 'RiskScore':
        """Predict risk score by constructing a synthetic CommitAnalysis."""
        # Map string component_type to enum
        try:
            ct = ComponentType(component_type)
        except ValueError:
            ct = ComponentType.FUNCTION

        from app.models.change_models import ImpactedComponent, AffectedAPI
        from app.models.risk_models import RiskScore

        # Build a synthetic CommitAnalysis for the risk engine
        direct_impact_models = [
            ImpactedComponent(
                component_id=d, component_type=ct,
                impact_type='direct', source_changes=[component_id],
            )
            for d in direct_impact
        ]
        transitive_impact_models = [
            ImpactedComponent(
                component_id=t, component_type=ct,
                impact_type='transitive', source_changes=[component_id],
            )
            for t in transitive_impact
        ]
        affected_api_models = [
            AffectedAPI(
                route_path=a.route_path, http_method=a.http_method,
                function_name=a.function_name, file_path=a.file_path,
                impact_type='simulated',
            )
            for a in affected_apis
        ]

        synthetic_analysis = CommitAnalysis(
            repository_path='<simulation>',
            commit=CommitInfo(
                commit_hash='0' * 40,
                short_hash='simulated',
                author='WhatIf Simulator',
                author_email='whatif@scopeguard',
                message='Simulated change',
                timestamp='',
            ),
            changed_components=[
                ComponentChange(
                    component_id=component_id,
                    component_type=ct,
                    change_type=ComponentChangeType.MODIFIED,
                    file_path='<simulation>',
                    name=component_id.split(':')[-1] if ':' in component_id else component_id,
                ),
            ],
            direct_impact=direct_impact_models,
            transitive_impact=transitive_impact_models,
            affected_apis=affected_api_models,
            blast_radius=BlastRadius(
                changed_component_count=1,
                direct_impact_count=len(direct_impact),
                transitive_impact_count=len(transitive_impact),
                total_affected_count=1 + len(direct_impact) + len(transitive_impact),
                affected_api_count=len(affected_apis),
            ),
        )

        engine = RiskEngine()
        return engine.calculate(synthetic_analysis)
