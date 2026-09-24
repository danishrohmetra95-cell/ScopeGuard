"""Data models for test impact analysis and test selection.

These models represent discovered tests, their mappings to application
components, and the test selection result including priority and reasoning.

ScopeGuard NEVER executes tests from the analyzed repository.
All analysis is static — based on AST parsing of source files only.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class TestPriority(str, Enum):
    """Priority for running an impacted test."""
    HIGH = 'HIGH'
    MEDIUM = 'MEDIUM'
    LOW = 'LOW'


class TestCase(BaseModel):
    """A single test discovered via static analysis."""
    model_config = ConfigDict(from_attributes=True)

    test_id: str = Field(
        description='Unique ID: test_file::test_name',
    )
    test_file: str = Field(description='Path to the test file')
    test_name: str = Field(description='Test function/method name')
    class_name: str | None = Field(
        default=None,
        description='Enclosing test class name, if any',
    )
    line_number: int = Field(default=0, description='Line number of the test')
    module_name: str = Field(
        default='',
        description='Module name derived from the test file path',
    )


class TestMapping(BaseModel):
    """Mapping between a test and the application components it references."""
    model_config = ConfigDict(from_attributes=True)

    test_id: str = Field(description='Test identifier')
    referenced_modules: list[str] = Field(
        default_factory=list,
        description='Application modules imported by the test',
    )
    referenced_functions: list[str] = Field(
        default_factory=list,
        description='Application functions called by the test',
    )
    referenced_component_ids: list[str] = Field(
        default_factory=list,
        description='Component IDs matching the dependency graph',
    )


class TestImpact(BaseModel):
    """A test that is affected by a code change."""
    model_config = ConfigDict(from_attributes=True)

    test: TestCase = Field(description='The affected test')
    priority: TestPriority = Field(description='Suggested run priority')
    reason: str = Field(description='Human-readable reason for selection')
    affected_components: list[str] = Field(
        default_factory=list,
        description='Component IDs that link this test to the change',
    )
    impact_chain: str = Field(
        default='',
        description='Short chain showing test → component → change',
    )


class TestSelectionResult(BaseModel):
    """Complete test selection analysis for a commit."""
    model_config = ConfigDict(from_attributes=True)

    total_tests: int = Field(default=0, description='Total tests discovered')
    selected_tests: int = Field(
        default=0, description='Tests selected for execution',
    )
    skipped_tests: int = Field(
        default=0, description='Tests that can safely be skipped',
    )
    selection_percentage: float = Field(
        default=0.0,
        description='Percentage of tests selected (0-100)',
    )
    high_priority: list[TestImpact] = Field(
        default_factory=list, description='Tests that directly reference changes',
    )
    medium_priority: list[TestImpact] = Field(
        default_factory=list, description='Tests affected through dependencies',
    )
    low_priority: list[TestImpact] = Field(
        default_factory=list,
        description='Tests with weak/indirect association',
    )


class CommitTestAnalysis(BaseModel):
    """Full commit analysis with test selection.

    Combines M3 commit analysis fields with M5 test selection.
    """
    model_config = ConfigDict(from_attributes=True)

    repository_path: str = Field(description='Path to the analyzed repository')
    commit: 'CommitInfo' = Field(description='Analyzed commit')
    file_changes: list['FileChange'] = Field(default_factory=list)
    changed_components: list['ComponentChange'] = Field(default_factory=list)
    direct_impact: list['ImpactedComponent'] = Field(default_factory=list)
    transitive_impact: list['ImpactedComponent'] = Field(default_factory=list)
    blast_radius: 'BlastRadius' = Field(default_factory=lambda: BlastRadius())
    test_selection: TestSelectionResult = Field(
        default_factory=TestSelectionResult,
        description='Test impact analysis and selection',
    )


# Deferred imports to avoid circular dependencies
from app.models.change_models import (  # noqa: E402
    BlastRadius,
    CommitInfo,
    ComponentChange,
    FileChange,
    ImpactedComponent,
)

CommitTestAnalysis.model_rebuild()
