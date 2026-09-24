"""Data models for Pull Request analysis.

PR analysis compares two commits (base → head) and produces a
comprehensive risk report covering file changes, component changes,
impact, test selection, complexity delta, and hotspot status.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.models.change_models import (
    AffectedAPI,
    BlastRadius,
    CommitInfo,
    ComponentChange,
    FileChange,
    ImpactedComponent,
)
from app.models.risk_models import RiskScore
from app.models.test_models import TestSelectionResult


class PRAnalyzeRequest(BaseModel):
    """Request model for PR analysis."""
    model_config = ConfigDict(from_attributes=True)

    path: str = Field(description='Path to the Git repository')
    base_commit: str = Field(description='Base commit hash (e.g., main branch tip)')
    head_commit: str = Field(description='Head commit hash (e.g., PR branch tip)')


class ComplexityDelta(BaseModel):
    """Change in complexity metrics between base and head."""
    model_config = ConfigDict(from_attributes=True)

    total_functions_before: int = 0
    total_functions_after: int = 0
    functions_added: int = 0
    functions_removed: int = 0
    average_complexity_before: float = 0.0
    average_complexity_after: float = 0.0
    complexity_change_percentage: float = Field(
        default=0.0,
        description='Percentage change in average complexity',
    )
    most_complex_changed: list[str] = Field(
        default_factory=list,
        description='Component IDs of changed functions with highest complexity',
    )


class PRAnalysisResult(BaseModel):
    """Complete Pull Request analysis result."""
    model_config = ConfigDict(from_attributes=True)

    repository_path: str = Field(description='Path to the analyzed repository')
    base_commit: CommitInfo = Field(description='Base commit info')
    head_commit: CommitInfo = Field(description='Head commit info')

    # File-level changes
    file_changes: list[FileChange] = Field(default_factory=list)
    total_additions: int = Field(default=0, description='Total lines added across all files')
    total_deletions: int = Field(default=0, description='Total lines removed across all files')

    # Component-level changes
    changed_components: list[ComponentChange] = Field(default_factory=list)

    # Impact
    direct_impact: list[ImpactedComponent] = Field(default_factory=list)
    transitive_impact: list[ImpactedComponent] = Field(default_factory=list)
    affected_apis: list[AffectedAPI] = Field(default_factory=list)
    blast_radius: BlastRadius = Field(default_factory=BlastRadius)

    # Tests
    test_selection: TestSelectionResult = Field(
        default_factory=TestSelectionResult,
        description='Recommended tests to run',
    )

    # Complexity
    complexity_delta: ComplexityDelta = Field(
        default_factory=ComplexityDelta,
        description='Change in code complexity',
    )

    # Hotspots
    hotspots_touched: list[str] = Field(
        default_factory=list,
        description='Component IDs of hotspots affected by this PR',
    )
    hotspot_count: int = Field(default=0)

    # Risk
    risk: RiskScore = Field(
        default_factory=RiskScore,
        description='Regression risk assessment',
    )
