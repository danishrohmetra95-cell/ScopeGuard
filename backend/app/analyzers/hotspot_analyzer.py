"""Engineering hotspot analyzer.

Combines four dimensions into a deterministic hotspot score:

    hotspot_score = (complexity × W1) + (dependency_centrality × W2)
                  + (change_frequency × W3) + (impact_reach × W4)

Dimensions:
    1. Complexity — average cyclomatic complexity of functions in the component
    2. Dependency centrality — in-degree + out-degree in the dependency graph
    3. Change frequency — how often the component has changed (from history)
    4. Impact reach — number of direct + transitive dependents

All dimensions are normalized to 0-100 before applying weights.
The final score is deterministic and reproducible.

Weights (documented, tunable):
    W1 = 0.30  (complexity)
    W2 = 0.25  (dependency centrality)
    W3 = 0.25  (change frequency)
    W4 = 0.20  (impact reach)
"""

import logging
from pathlib import Path

from app.analyzers.complexity_analyzer import ComplexityAnalyzer
from app.analyzers.dependency_graph import DependencyGraphBuilder
from app.analyzers.repository_scanner import RepositoryScanner
from app.models.analysis_models import RepositoryAnalysis
from app.models.complexity_models import (
    ComplexityResult,
    FunctionComplexity,
    HotspotComponent,
    HotspotMethodology,
    HotspotReason,
    HotspotResult,
)
from app.models.graph_models import DependencyAnalysis

logger = logging.getLogger(__name__)

# Scoring weights — documented constants
W_COMPLEXITY = 0.30
W_DEPENDENCY = 0.25
W_CHANGE_FREQ = 0.25
W_IMPACT = 0.20

# Hotspot threshold
_HOTSPOT_THRESHOLD = 40.0

# Normalization caps (to prevent outliers from dominating)
_MAX_COMPLEXITY = 30       # cyclomatic complexity cap
_MAX_DEGREE = 20           # total degree cap
_MAX_CHANGE_COUNT = 15     # change count cap
_MAX_IMPACT = 30           # dependent count cap


def _normalize(value: float, max_val: float) -> float:
    """Normalize a value to 0-100, capped at max_val."""
    if max_val <= 0:
        return 0.0
    return min(100.0, (value / max_val) * 100.0)


class HotspotAnalyzer:
    """Identifies engineering hotspots by combining structural complexity,
    dependency centrality, change frequency, and impact reach.

    All scoring is deterministic. No AI/LLM is used.
    """

    def analyze_hotspots(
        self,
        repo_path: Path,
        repo_analysis: RepositoryAnalysis | None = None,
        change_frequency: dict[str, int] | None = None,
    ) -> HotspotResult:
        """Analyze a repository for engineering hotspots.

        Args:
            repo_path: Path to the repository.
            repo_analysis: Pre-computed repository analysis (optional).
            change_frequency: Optional dict mapping component_id -> change count
                            (from historical analysis). If None, change frequency
                            dimension scores 0.

        Returns:
            HotspotResult with scored components and methodology.
        """
        # Step 1: Scan repository
        if repo_analysis is None:
            scanner = RepositoryScanner()
            repo_analysis = scanner.scan(repo_path)

        # Step 2: Build dependency graph
        graph_builder = DependencyGraphBuilder()
        dep_analysis = graph_builder.build(repo_analysis)

        # Step 3: Compute complexity
        complexity_analyzer = ComplexityAnalyzer()
        complexity_result = complexity_analyzer.analyze_repository(
            repo_path, repo_analysis=repo_analysis, graph_builder=graph_builder,
        )

        # Step 4: Build hotspot scores for all components in the graph
        hotspots = self._score_components(
            graph_builder=graph_builder,
            dep_analysis=dep_analysis,
            complexity_result=complexity_result,
            change_frequency=change_frequency or {},
        )

        # Sort by hotspot score descending
        hotspots.sort(key=lambda h: h.hotspot_score, reverse=True)

        hotspot_count = sum(1 for h in hotspots if h.hotspot_score >= _HOTSPOT_THRESHOLD)

        return HotspotResult(
            repository_path=str(repo_path),
            hotspots=hotspots,
            methodology=HotspotMethodology(),
            total_components_analyzed=len(hotspots),
            hotspot_count=hotspot_count,
        )

    def _score_components(
        self,
        graph_builder: DependencyGraphBuilder,
        dep_analysis: DependencyAnalysis,
        complexity_result: ComplexityResult,
        change_frequency: dict[str, int],
    ) -> list[HotspotComponent]:
        """Score every component across all four dimensions."""
        graph = graph_builder.graph

        # Build complexity lookup: component_id -> max complexity in that component
        complexity_by_component: dict[str, float] = {}
        for fc in complexity_result.functions:
            # For individual functions, use their own complexity
            complexity_by_component[fc.component_id] = float(fc.cyclomatic_complexity)

            # For module-level hotspots: aggregate max complexity of functions in that module
            # Extract module component_id from the function's component_id
            parts = fc.component_id.split(':', 1)
            if len(parts) == 2:
                dotted = parts[1]
                # module_name is everything before the last dot for functions
                if '.' in dotted:
                    module_name = dotted.rsplit('.', 1)[0]
                    # Handle methods: method:mod.Class.method -> mod
                    if parts[0] == 'method' and module_name.count('.') >= 1:
                        module_name = module_name.rsplit('.', 1)[0]
                    module_id = f'module:{module_name}'
                    existing = complexity_by_component.get(module_id, 0.0)
                    complexity_by_component[module_id] = max(existing, float(fc.cyclomatic_complexity))

        results: list[HotspotComponent] = []

        for node in dep_analysis.nodes:
            cid = node.component_id
            ctype = node.component_type.value

            # Dimension 1: Complexity
            raw_complexity = complexity_by_component.get(cid, 0.0)
            norm_complexity = _normalize(raw_complexity, _MAX_COMPLEXITY)

            # Dimension 2: Dependency centrality
            in_deg = graph.in_degree(cid) if cid in graph else 0
            out_deg = graph.out_degree(cid) if cid in graph else 0
            raw_degree = float(in_deg + out_deg)
            norm_dependency = _normalize(raw_degree, _MAX_DEGREE)

            # Dimension 3: Change frequency
            raw_change = float(change_frequency.get(cid, 0))
            norm_change = _normalize(raw_change, _MAX_CHANGE_COUNT)

            # Dimension 4: Impact reach (direct + transitive dependents)
            try:
                direct = graph_builder.get_direct_dependents(cid)
                transitive = graph_builder.get_transitive_dependents(cid)
                raw_impact = float(len(direct) + len(transitive))
            except KeyError:
                raw_impact = 0.0
            norm_impact = _normalize(raw_impact, _MAX_IMPACT)

            # Weighted score
            w_complexity = norm_complexity * W_COMPLEXITY
            w_dependency = norm_dependency * W_DEPENDENCY
            w_change = norm_change * W_CHANGE_FREQ
            w_impact = norm_impact * W_IMPACT
            hotspot_score = round(w_complexity + w_dependency + w_change + w_impact, 2)

            # Build reasons
            reasons: list[HotspotReason] = []
            if norm_complexity > 0:
                reasons.append(HotspotReason(
                    dimension='complexity',
                    description=f'Cyclomatic complexity of {raw_complexity:.0f}',
                    raw_value=raw_complexity,
                    normalized_value=round(norm_complexity, 2),
                    weighted_contribution=round(w_complexity, 2),
                ))
            if norm_dependency > 0:
                reasons.append(HotspotReason(
                    dimension='dependency',
                    description=f'{in_deg} dependents, {out_deg} dependencies (total degree {in_deg + out_deg})',
                    raw_value=raw_degree,
                    normalized_value=round(norm_dependency, 2),
                    weighted_contribution=round(w_dependency, 2),
                ))
            if norm_change > 0:
                reasons.append(HotspotReason(
                    dimension='change_frequency',
                    description=f'Changed {int(raw_change)} times in recent history',
                    raw_value=raw_change,
                    normalized_value=round(norm_change, 2),
                    weighted_contribution=round(w_change, 2),
                ))
            if norm_impact > 0:
                reasons.append(HotspotReason(
                    dimension='impact',
                    description=f'{int(raw_impact)} components affected if this changes',
                    raw_value=raw_impact,
                    normalized_value=round(norm_impact, 2),
                    weighted_contribution=round(w_impact, 2),
                ))

            results.append(HotspotComponent(
                component_id=cid,
                component_type=ctype,
                file_path=node.file_path,
                hotspot_score=hotspot_score,
                reasons=reasons,
                complexity_score=round(w_complexity, 2),
                dependency_score=round(w_dependency, 2),
                change_frequency_score=round(w_change, 2),
                impact_score=round(w_impact, 2),
            ))

        return results
