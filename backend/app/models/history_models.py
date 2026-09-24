"""Data models for historical change intelligence.

These models represent aggregated historical analysis of Git commits
including component hotspots, risk trends, and change frequency.

IMPORTANT: Hotspots indicate frequently changed components with high
historical impact. They do NOT imply bugs, regressions, or production
failures. Only information derivable from Git history and ScopeGuard's
deterministic analysis is reported.
"""

from pydantic import BaseModel, ConfigDict, Field


class HistoricalCommit(BaseModel):
    """Summary of a single analyzed commit in historical context."""
    model_config = ConfigDict(from_attributes=True)

    commit_hash: str = Field(description='Full commit hash')
    short_hash: str = Field(description='Short (7-char) commit hash')
    author: str = Field(description='Author name')
    message: str = Field(description='Commit message')
    timestamp: str = Field(description='ISO 8601 timestamp')
    changed_file_count: int = Field(default=0)
    changed_component_count: int = Field(default=0)
    direct_impact_count: int = Field(default=0)
    transitive_impact_count: int = Field(default=0)
    affected_api_count: int = Field(default=0)
    risk_score: int = Field(default=0)
    risk_level: str = Field(default='LOW')
    selected_test_count: int = Field(default=0)


class ComponentHistory(BaseModel):
    """Aggregated change history for a single component."""
    model_config = ConfigDict(from_attributes=True)

    component_id: str = Field(description='Component ID')
    change_count: int = Field(default=0, description='Total times changed')
    modification_count: int = Field(default=0)
    addition_count: int = Field(default=0)
    removal_count: int = Field(default=0)
    average_risk: float = Field(default=0.0)
    max_risk: int = Field(default=0)
    total_direct_impact: int = Field(default=0)
    total_transitive_impact: int = Field(default=0)
    hotspot_score: float = Field(
        default=0.0,
        description='Deterministic hotspot score (higher = more active)',
    )


class FrequentlyAffectedComponent(BaseModel):
    """A component that is frequently impacted by changes to other components."""
    model_config = ConfigDict(from_attributes=True)

    component_id: str = Field(description='The affected component')
    times_affected: int = Field(
        default=0, description='How many commits affected this component',
    )
    source_components: list[str] = Field(
        default_factory=list,
        description='Components whose changes trigger impact on this one',
    )


class RiskTrendPoint(BaseModel):
    """A single data point in the risk trend."""
    model_config = ConfigDict(from_attributes=True)

    commit_hash: str = Field(description='Short commit hash')
    timestamp: str = Field(description='Commit timestamp')
    score: int = Field(description='Risk score')
    risk_level: str = Field(description='Risk level')


class RiskTrendSummary(BaseModel):
    """Aggregated risk statistics across analyzed commits."""
    model_config = ConfigDict(from_attributes=True)

    average_risk: float = Field(default=0.0)
    highest_risk: int = Field(default=0)
    lowest_risk: int = Field(default=0)
    low_count: int = Field(default=0)
    medium_count: int = Field(default=0)
    high_count: int = Field(default=0)
    critical_count: int = Field(default=0)


class HistoricalAnalysisResult(BaseModel):
    """Complete result of historical change intelligence analysis."""
    model_config = ConfigDict(from_attributes=True)

    repository_path: str = Field(description='Analyzed repository')
    graph_basis: str = Field(
        default='current_head',
        description='The dependency graph basis used for historical impact analysis (current_head vs reconstructed)',
    )
    commits_analyzed: list[HistoricalCommit] = Field(
        default_factory=list,
        description='Per-commit summaries in chronological order',
    )
    commit_count: int = Field(default=0)
    component_hotspots: list[ComponentHistory] = Field(
        default_factory=list,
        description='Components sorted by hotspot score (descending)',
    )
    risk_trend: list[RiskTrendPoint] = Field(
        default_factory=list,
        description='Chronological risk scores',
    )
    risk_trend_summary: RiskTrendSummary = Field(
        default_factory=RiskTrendSummary,
    )
    high_risk_commits: list[HistoricalCommit] = Field(
        default_factory=list,
        description='Commits with HIGH or CRITICAL risk',
    )
    frequently_changed_components: list[ComponentHistory] = Field(
        default_factory=list,
        description='Components changed 2+ times, sorted by count',
    )
    frequently_affected_components: list[FrequentlyAffectedComponent] = Field(
        default_factory=list,
        description='Components most frequently impacted by other changes',
    )
    summary: str = Field(default='', description='Human-readable summary')
    insights: list[str] = Field(
        default_factory=list,
        description='Deterministic textual insights',
    )


class HistoryAnalyzeRequest(BaseModel):
    """Request model for historical analysis."""
    model_config = ConfigDict(from_attributes=True)

    path: str = Field(description='Path to the Git repository')
    limit: int = Field(
        default=20, ge=1, le=100,
        description='Number of recent commits to analyze (1-100)',
    )
