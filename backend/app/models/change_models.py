"""Data models for Git change analysis and impact assessment.

Defines structured representations for commit information, file changes,
component-level changes, impact results, and blast radius statistics.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.models.graph_models import ComponentType


class ChangeType(str, Enum):
    """Type of change to a file in a Git commit."""
    ADDED = 'added'
    MODIFIED = 'modified'
    DELETED = 'deleted'
    RENAMED = 'renamed'


class ComponentChangeType(str, Enum):
    """Type of change to a code component (function, class, method)."""
    ADDED = 'added'
    REMOVED = 'removed'
    MODIFIED = 'modified'


class CommitInfo(BaseModel):
    """Information about a Git commit."""
    model_config = ConfigDict(from_attributes=True)

    commit_hash: str = Field(description='Full 40-character commit hash')
    short_hash: str = Field(description='Short (7-character) commit hash')
    author: str = Field(description='Author name')
    author_email: str = Field(description='Author email address')
    message: str = Field(description='Commit message')
    timestamp: str = Field(description='Commit timestamp in ISO 8601 format')
    parent_hash: str | None = Field(
        default=None,
        description='First parent commit hash, None for initial commits',
    )
    changed_file_count: int = Field(default=0, description='Number of files changed')


class FileChange(BaseModel):
    """A file changed in a Git commit."""
    model_config = ConfigDict(from_attributes=True)

    path: str = Field(description='File path relative to repository root')
    change_type: ChangeType = Field(description='Type of change')
    old_path: str | None = Field(
        default=None, description='Previous path for renamed files',
    )
    additions: int = Field(default=0, description='Number of lines added')
    deletions: int = Field(default=0, description='Number of lines deleted')


class ComponentChange(BaseModel):
    """A code component that changed between commit versions.

    Component IDs follow the dependency graph convention:
        function:module_name.func_name
        class:module_name.ClassName
        method:module_name.ClassName.method_name
        module:module_name
    """
    model_config = ConfigDict(from_attributes=True)

    component_id: str = Field(
        description='Stable component ID matching the dependency graph',
    )
    component_type: ComponentType = Field(description='Type of component')
    change_type: ComponentChangeType = Field(description='How the component changed')
    file_path: str = Field(description='File containing the component')
    name: str = Field(description='Component short name')
    old_line_range: list[int] | None = Field(
        default=None, description='[start, end] line numbers in old version',
    )
    new_line_range: list[int] | None = Field(
        default=None, description='[start, end] line numbers in new version',
    )
    change_semantics: str | None = Field(
        default=None, description='Semantic classification of the change (e.g., whitespace-only, documentation-only)',
    )


class ImpactedComponent(BaseModel):
    """A component affected by changes via the dependency graph."""
    model_config = ConfigDict(from_attributes=True)

    component_id: str = Field(description='Affected component ID')
    component_type: ComponentType = Field(description='Type of affected component')
    impact_type: str = Field(description="'direct' or 'transitive'")
    source_changes: list[str] = Field(
        default_factory=list,
        description='Component IDs of the changes that caused this impact',
    )


class AffectedAPI(BaseModel):
    """An API route potentially affected by changes."""
    model_config = ConfigDict(from_attributes=True)

    route_path: str | None = Field(default=None, description='Route path')
    http_method: str = Field(description='HTTP method (GET, POST, etc.)')
    function_name: str = Field(description='Handler function name')
    file_path: str = Field(description='File containing the route')
    impact_type: str = Field(description="'direct' or 'transitive'")


class BlastRadius(BaseModel):
    """Summary statistics for the overall impact of changes.

    Definitions:
        Direct Impact: components with a direct dependency on a changed component.
        Transitive Impact: components reachable through dependency chains.
        Blast Radius: the total set of potentially affected components.
    """
    model_config = ConfigDict(from_attributes=True)

    changed_file_count: int = Field(default=0)
    changed_component_count: int = Field(default=0)
    direct_impact_count: int = Field(default=0)
    transitive_impact_count: int = Field(default=0)
    total_affected_count: int = Field(
        default=0,
        description='Total unique affected components (changed + direct + transitive)',
    )
    affected_module_count: int = Field(default=0)
    affected_function_count: int = Field(default=0)
    affected_class_count: int = Field(default=0)
    affected_method_count: int = Field(default=0)
    affected_api_count: int = Field(default=0)


class CommitAnalysis(BaseModel):
    """Complete analysis of a Git commit and its impact on the codebase."""
    model_config = ConfigDict(from_attributes=True)

    repository_path: str = Field(description='Path to the analyzed repository')
    commit: CommitInfo = Field(description='Analyzed commit information')
    file_changes: list[FileChange] = Field(
        default_factory=list, description='Files changed in the commit',
    )
    changed_components: list[ComponentChange] = Field(
        default_factory=list, description='Components that changed',
    )
    direct_impact: list[ImpactedComponent] = Field(
        default_factory=list, description='Directly impacted components',
    )
    transitive_impact: list[ImpactedComponent] = Field(
        default_factory=list, description='Transitively impacted components',
    )
    affected_apis: list[AffectedAPI] = Field(
        default_factory=list, description='API routes potentially affected',
    )
    blast_radius: BlastRadius = Field(
        default_factory=BlastRadius, description='Impact summary statistics',
    )


class CommitAnalyzeRequest(BaseModel):
    """Request model for commit analysis."""
    model_config = ConfigDict(from_attributes=True)

    path: str = Field(description='Path to the Git repository')
    commit: str = Field(description='Commit hash to analyze')
