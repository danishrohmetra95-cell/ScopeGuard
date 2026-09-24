"""Data models for code complexity and engineering hotspot analysis.

Complexity scoring is entirely static and deterministic — based on
AST analysis of function/method bodies. No code is executed.

Hotspot scoring combines structural complexity with dependency centrality
and historical change frequency using documented, weighted rules.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ComplexityRating(str, Enum):
    """Cyclomatic complexity rating thresholds.

    Based on standard software engineering thresholds:
        1-5   = LOW       — simple, well-structured code
        6-10  = MODERATE  — acceptable complexity
        11-20 = HIGH      — consider refactoring
        21+   = VERY_HIGH — urgent refactoring recommended
    """
    LOW = 'LOW'
    MODERATE = 'MODERATE'
    HIGH = 'HIGH'
    VERY_HIGH = 'VERY_HIGH'


class FunctionComplexity(BaseModel):
    """Complexity metrics for a single function or method."""
    model_config = ConfigDict(from_attributes=True)

    component_id: str = Field(description='Stable component ID matching the dependency graph')
    name: str = Field(description='Function/method name')
    qualified_name: str = Field(description='Qualified name including class if applicable')
    file_path: str = Field(description='File containing the function')
    line_number: int = Field(default=0, description='Start line number')
    end_line: int | None = Field(default=None, description='End line number')

    # Core metrics
    cyclomatic_complexity: int = Field(default=1, description='Cyclomatic complexity (branches + 1)')
    lines_of_code: int = Field(default=0, description='Lines of code in the function body')
    branch_count: int = Field(default=0, description='Number of branch points (if/elif/else)')
    loop_count: int = Field(default=0, description='Number of loops (for/while)')
    call_count: int = Field(default=0, description='Number of function/method calls')
    parameter_count: int = Field(default=0, description='Number of parameters')
    max_nesting_depth: int = Field(default=0, description='Maximum nesting depth of control flow')

    # Graph metrics (populated when dependency graph is available)
    dependency_count: int = Field(default=0, description='Number of outgoing dependencies')
    dependent_count: int = Field(default=0, description='Number of components that depend on this')

    # Rating
    rating: ComplexityRating = Field(
        default=ComplexityRating.LOW,
        description='Complexity rating based on cyclomatic complexity',
    )

    is_method: bool = Field(default=False, description='Whether this is a class method')


class ComplexitySummary(BaseModel):
    """Aggregate complexity statistics for a repository."""
    model_config = ConfigDict(from_attributes=True)

    total_functions: int = Field(default=0)
    average_complexity: float = Field(default=0.0)
    median_complexity: float = Field(default=0.0)
    max_complexity: int = Field(default=0)
    low_count: int = Field(default=0, description='Functions with LOW complexity')
    moderate_count: int = Field(default=0, description='Functions with MODERATE complexity')
    high_count: int = Field(default=0, description='Functions with HIGH complexity')
    very_high_count: int = Field(default=0, description='Functions with VERY_HIGH complexity')
    total_lines_of_code: int = Field(default=0)


class ComplexityResult(BaseModel):
    """Complete complexity analysis for a repository."""
    model_config = ConfigDict(from_attributes=True)

    repository_path: str = Field(description='Path to the analyzed repository')
    functions: list[FunctionComplexity] = Field(
        default_factory=list,
        description='Complexity metrics for every function/method',
    )
    summary: ComplexitySummary = Field(
        default_factory=ComplexitySummary,
        description='Aggregate complexity statistics',
    )
    most_complex: list[FunctionComplexity] = Field(
        default_factory=list,
        description='Top 20 most complex functions, sorted by cyclomatic complexity',
    )


class HotspotReason(BaseModel):
    """A single reason why a component is considered a hotspot."""
    model_config = ConfigDict(from_attributes=True)

    dimension: str = Field(description='Which dimension contributed (complexity/dependency/change_frequency/impact)')
    description: str = Field(description='Human-readable explanation')
    raw_value: float = Field(default=0.0, description='Raw metric value before normalization')
    normalized_value: float = Field(default=0.0, description='Normalized contribution (0-1)')
    weighted_contribution: float = Field(default=0.0, description='Final weighted contribution to hotspot score')


class HotspotComponent(BaseModel):
    """A component identified as an engineering hotspot."""
    model_config = ConfigDict(from_attributes=True)

    component_id: str = Field(description='Component ID matching the dependency graph')
    component_type: str = Field(description='module/class/function/method')
    file_path: str | None = Field(default=None)
    hotspot_score: float = Field(default=0.0, description='Combined hotspot score (0-100)')
    reasons: list[HotspotReason] = Field(
        default_factory=list,
        description='Breakdown of why this is a hotspot',
    )

    # Individual dimension scores
    complexity_score: float = Field(default=0.0, description='Complexity contribution')
    dependency_score: float = Field(default=0.0, description='Dependency centrality contribution')
    change_frequency_score: float = Field(default=0.0, description='Change frequency contribution')
    impact_score: float = Field(default=0.0, description='Impact reach contribution')


class HotspotMethodology(BaseModel):
    """Documents the deterministic hotspot scoring formula."""
    model_config = ConfigDict(from_attributes=True)

    formula: str = Field(
        default=(
            'hotspot_score = (complexity × 0.30) + (dependency_centrality × 0.25) '
            '+ (change_frequency × 0.25) + (impact_reach × 0.20)'
        ),
    )
    complexity_weight: float = Field(default=0.30)
    dependency_weight: float = Field(default=0.25)
    change_frequency_weight: float = Field(default=0.25)
    impact_weight: float = Field(default=0.20)
    description: str = Field(
        default=(
            'Hotspot score combines four dimensions: structural code complexity '
            '(cyclomatic complexity of functions), dependency centrality '
            '(in-degree + out-degree in the dependency graph), historical change '
            'frequency (how often the component has changed), and impact reach '
            '(number of direct + transitive dependents). All dimensions are '
            'normalized to 0-100 before weighting. The final score is deterministic '
            'and reproducible.'
        ),
    )


class HotspotResult(BaseModel):
    """Complete hotspot analysis for a repository."""
    model_config = ConfigDict(from_attributes=True)

    repository_path: str = Field(description='Path to the analyzed repository')
    hotspots: list[HotspotComponent] = Field(
        default_factory=list,
        description='Components sorted by hotspot score (highest first)',
    )
    methodology: HotspotMethodology = Field(
        default_factory=HotspotMethodology,
        description='Documented scoring methodology',
    )
    total_components_analyzed: int = Field(default=0)
    hotspot_count: int = Field(
        default=0,
        description='Number of components above hotspot threshold (score >= 40)',
    )
