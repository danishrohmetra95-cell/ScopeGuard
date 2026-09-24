"""Data models for the deterministic regression risk engine.

Risk scoring is entirely rule-based and deterministic — no AI/LLM is used.
The score is calculated from measurable engineering signals produced by
the commit analysis pipeline (M1-M3).
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class RiskLevel(str, Enum):
    """Regression risk severity level.

    Thresholds:
        0-24  = LOW
        25-49 = MEDIUM
        50-74 = HIGH
        75-100 = CRITICAL
    """
    LOW = 'LOW'
    MEDIUM = 'MEDIUM'
    HIGH = 'HIGH'
    CRITICAL = 'CRITICAL'


class RiskFactor(BaseModel):
    """A single contributing factor to the risk score.

    Each factor represents a measurable engineering signal with a
    deterministic point contribution.
    """
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(description='Factor identifier')
    description: str = Field(description='Human-readable explanation')
    points: int = Field(description='Point contribution to the score')
    severity: str = Field(
        default='info',
        description="Importance: 'info', 'warning', or 'critical'",
    )
    measured_value: str | int | float | None = Field(default=None, description='Actual measured value')
    rule: str | None = Field(default=None, description='Threshold or rule that triggered it')
    evidence: list[str] = Field(default_factory=list, description='Evidence supporting the factor')


class RiskContributor(BaseModel):
    """A risk contributor with human-readable labeling and percentage."""
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(description='Factor identifier')
    human_label: str = Field(description='Human-readable label for display')
    points: int = Field(description='Point contribution')
    percentage: float = Field(default=0.0, description='Percentage of total score')
    description: str = Field(default='', description='Short explanation')
    measured_value: str | int | float | None = Field(default=None, description='Actual measured value')
    rule: str | None = Field(default=None, description='Threshold or rule that triggered it')
    evidence: list[str] = Field(default_factory=list, description='Evidence supporting the contribution')


class RiskScore(BaseModel):
    """Complete risk assessment for a commit."""
    model_config = ConfigDict(from_attributes=True)

    score: int = Field(
        default=0, ge=0, le=100,
        description='Deterministic risk score from 0 to 100',
    )
    level: RiskLevel = Field(
        default=RiskLevel.LOW,
        description='Risk severity level',
    )
    factors: list[RiskFactor] = Field(
        default_factory=list,
        description='Contributing risk factors with explanations',
    )
    summary: str = Field(
        default='',
        description='Human-readable risk summary',
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description='Actionable recommendations based on risk level',
    )
    explanation: str = Field(
        default='',
        description='Human-readable narrative explaining the risk score',
    )
    contributor_breakdown: list[RiskContributor] = Field(
        default_factory=list,
        description='Ordered breakdown of risk contributors with percentages',
    )


class CommitRiskAnalysis(BaseModel):
    """Full commit analysis with risk scoring.

    Extends the M3 CommitAnalysis with deterministic risk assessment.
    Re-uses the M3 fields by composition rather than inheritance to
    keep the existing CommitAnalysis model unchanged.
    """
    model_config = ConfigDict(from_attributes=True)

    repository_path: str = Field(description='Path to the analyzed repository')

    # M3 fields (re-exported for a single response)
    commit: 'CommitInfo' = Field(description='Analyzed commit')
    file_changes: list['FileChange'] = Field(default_factory=list)
    changed_components: list['ComponentChange'] = Field(default_factory=list)
    direct_impact: list['ImpactedComponent'] = Field(default_factory=list)
    transitive_impact: list['ImpactedComponent'] = Field(default_factory=list)
    affected_apis: list['AffectedAPI'] = Field(default_factory=list)
    blast_radius: 'BlastRadius' = Field(default_factory=lambda: BlastRadius())

    # M4 risk assessment
    risk: RiskScore = Field(
        default_factory=RiskScore,
        description='Deterministic regression risk assessment',
    )


# Deferred imports to avoid circular dependencies
from app.models.change_models import (  # noqa: E402
    AffectedAPI,
    BlastRadius,
    CommitInfo,
    ComponentChange,
    FileChange,
    ImpactedComponent,
)

CommitRiskAnalysis.model_rebuild()
