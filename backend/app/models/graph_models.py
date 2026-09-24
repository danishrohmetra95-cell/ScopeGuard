"""Data models for the dependency graph engine.

Defines component types, dependency relationships, and structured
response models for the graph analysis API.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ComponentType(str, Enum):
    """Types of code components represented as graph nodes."""
    MODULE = 'module'
    CLASS = 'class'
    FUNCTION = 'function'
    METHOD = 'method'


class DependencyType(str, Enum):
    """Types of dependency relationships represented as graph edges."""
    IMPORTS = 'imports'
    CALLS = 'calls'
    CONTAINS = 'contains'


class DependencyClassification(str, Enum):
    """Classification of code components/dependencies."""
    FIRST_PARTY = 'FIRST_PARTY'
    THIRD_PARTY = 'THIRD_PARTY'
    STANDARD_LIBRARY = 'STANDARD_LIBRARY'
    UNRESOLVED = 'UNRESOLVED'


class ComponentNode(BaseModel):
    """A node in the dependency graph representing a code component."""
    model_config = ConfigDict(from_attributes=True)

    component_id: str = Field(description='Stable unique identifier, e.g. module:payment_service')
    component_type: ComponentType = Field(description='Type of code component')
    name: str = Field(description='Short name of the component')
    file_path: str | None = Field(default=None, description='Relative file path within the repository')
    line_number: int | None = Field(default=None, description='Line number where the component is defined')
    classification: DependencyClassification = Field(default=DependencyClassification.FIRST_PARTY, description='Classification of the component')
    metadata: dict[str, str | int | bool | None] = Field(
        default_factory=dict,
        description='Additional metadata about the component',
    )


class DependencyEdge(BaseModel):
    """An edge in the dependency graph representing a dependency."""
    model_config = ConfigDict(from_attributes=True)

    source: str = Field(description='Source component ID (the dependent)')
    target: str = Field(description='Target component ID (the dependency)')
    dependency_type: DependencyType = Field(description='Type of dependency')
    metadata: dict[str, str | int | bool | None] = Field(
        default_factory=dict,
        description='Additional metadata about the dependency',
    )


class UnresolvedDependency(BaseModel):
    """A dependency that could not be resolved to a known component.

    Python is dynamically typed, so many call targets and import references
    cannot be determined through static analysis alone.
    """
    model_config = ConfigDict(from_attributes=True)

    source: str = Field(description='Source component ID where the reference occurs')
    raw_name: str = Field(description='The unresolved name as it appears in source code')
    dependency_type: DependencyType = Field(description='What kind of dependency was attempted')
    reason: str = Field(default='Cannot resolve target statically', description='Why resolution failed')
    file_path: str | None = Field(default=None, description='File where the unresolved reference occurs')
    line_number: int | None = Field(default=None, description='Line number of the unresolved reference')


class HighConnectivityComponent(BaseModel):
    """A component with notably high connectivity in the graph."""
    model_config = ConfigDict(from_attributes=True)

    component_id: str
    component_type: ComponentType
    in_degree: int = Field(description='Number of components that depend on this one')
    out_degree: int = Field(description='Number of components this one depends on')
    total_degree: int = Field(description='Total connections (in + out)')


class GraphStatistics(BaseModel):
    """Aggregate statistics about the dependency graph."""
    model_config = ConfigDict(from_attributes=True)

    total_nodes: int = 0
    total_edges: int = 0
    module_count: int = 0
    class_count: int = 0
    function_count: int = 0
    method_count: int = 0
    import_edges: int = 0
    call_edges: int = 0
    contains_edges: int = 0
    unresolved_count: int = 0
    connected_components: int = Field(
        default=0,
        description='Number of weakly connected components in the graph',
    )
    highest_in_degree: list[HighConnectivityComponent] = Field(
        default_factory=list,
        description='Top nodes by in-degree (most depended upon)',
    )
    highest_out_degree: list[HighConnectivityComponent] = Field(
        default_factory=list,
        description='Top nodes by out-degree (most dependencies)',
    )


class ImpactResult(BaseModel):
    """Result of an impact traversal for a given component."""
    model_config = ConfigDict(from_attributes=True)

    component_id: str = Field(description='The component being analyzed for impact')
    direct_dependents: list[str] = Field(
        default_factory=list,
        description='Component IDs that directly depend on this component',
    )
    transitive_dependents: list[str] = Field(
        default_factory=list,
        description='All component IDs transitively affected by changes to this component',
    )
    direct_count: int = 0
    transitive_count: int = 0


class DependencyAnalysis(BaseModel):
    """Complete dependency graph analysis result."""
    model_config = ConfigDict(from_attributes=True)

    repository_path: str = Field(description='Path to the analyzed repository')
    statistics: GraphStatistics = Field(default_factory=GraphStatistics)
    nodes: list[ComponentNode] = Field(default_factory=list)
    edges: list[DependencyEdge] = Field(default_factory=list)
    unresolved: list[UnresolvedDependency] = Field(
        default_factory=list,
        description='Dependencies that could not be resolved statically',
    )
    high_connectivity: list[HighConnectivityComponent] = Field(
        default_factory=list,
        description='Components with the highest connectivity',
    )
