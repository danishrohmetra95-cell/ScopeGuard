"""Data models for the What-If impact simulator.

The What-If simulator predicts the impact of a hypothetical change
to a component without actually modifying the repository. All results
are clearly labeled as SIMULATION / PREDICTION.
"""

from pydantic import BaseModel, ConfigDict, Field


class WhatIfRequest(BaseModel):
    """Request model for What-If simulation."""
    model_config = ConfigDict(from_attributes=True)

    path: str = Field(description='Path to the Git repository')
    component_id: str = Field(
        description='Component ID to simulate a change for '
        '(e.g., function:payment_service.process_payment)',
    )


class WhatIfAffectedAPI(BaseModel):
    """An API route predicted to be affected."""
    model_config = ConfigDict(from_attributes=True)

    route_path: str | None = None
    http_method: str = ''
    function_name: str = ''
    file_path: str = ''
    impact_type: str = Field(default='simulated')


class WhatIfAffectedTest(BaseModel):
    """A test predicted to be affected."""
    model_config = ConfigDict(from_attributes=True)

    test_id: str = ''
    test_name: str = ''
    test_file: str = ''
    priority: str = Field(default='MEDIUM')
    reason: str = ''


class WhatIfBlastRadius(BaseModel):
    """Predicted blast radius from the simulated change."""
    model_config = ConfigDict(from_attributes=True)

    direct_impact_count: int = 0
    transitive_impact_count: int = 0
    total_affected_count: int = 0
    affected_api_count: int = 0
    affected_test_count: int = 0


class WhatIfResult(BaseModel):
    """Complete What-If simulation result.

    All results are labeled as simulation/prediction. This analysis
    is based on the static dependency graph — not an actual code change.
    """
    model_config = ConfigDict(from_attributes=True)

    simulation: bool = Field(
        default=True,
        description='Always True — marks this as a simulation, not actual analysis',
    )
    repository_path: str = Field(description='Path to the analyzed repository')
    component_id: str = Field(description='Component that was simulated as changed')
    component_type: str = Field(default='', description='Type of the component')
    component_name: str = Field(default='', description='Name of the component')
    file_path: str | None = Field(default=None)

    # Impact
    direct_impact: list[str] = Field(
        default_factory=list,
        description='Component IDs directly dependent on the simulated change',
    )
    transitive_impact: list[str] = Field(
        default_factory=list,
        description='Component IDs transitively affected',
    )
    affected_apis: list[WhatIfAffectedAPI] = Field(
        default_factory=list,
        description='API routes predicted to be affected',
    )
    affected_tests: list[WhatIfAffectedTest] = Field(
        default_factory=list,
        description='Tests predicted to need execution',
    )
    blast_radius: WhatIfBlastRadius = Field(
        default_factory=WhatIfBlastRadius,
    )

    # Risk
    predicted_risk_score: int = Field(
        default=0, ge=0, le=100,
        description='Predicted risk score based on static dependency analysis',
    )
    predicted_risk_level: str = Field(
        default='LOW',
        description='Predicted risk level (LOW/MEDIUM/HIGH/CRITICAL)',
    )
    risk_contributors: list[dict] = Field(
        default_factory=list,
        description='Breakdown of risk score contributors',
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description='Actionable recommendations based on predicted risk',
    )

    # Complexity / Hotspot (Phase 2 integration)
    complexity: dict | None = Field(
        default=None,
        description='Complexity metrics for the component (if available)',
    )
    hotspot: dict | None = Field(
        default=None,
        description='Hotspot scoring for the component (if available)',
    )

    # Metadata
    disclaimer: str = Field(
        default=(
            'This is a SIMULATION based on the static dependency graph. '
            'Actual impact may differ due to runtime behavior, dynamic '
            'imports, and code paths not captured by static analysis.'
        ),
    )
