"""Dependency graph builder for Python repository analysis.

Converts AST analysis results into a NetworkX directed graph representing
relationships between code components (modules, classes, functions, methods).

Graph direction convention:
    Edges point FROM the dependent TO the dependency.
    Example: A imports B  ->  edge from A to B.
    
    To find what is affected when B changes, traverse INCOMING edges to B
    (i.e. predecessors / reverse traversal). Components that depend on B
    are B's predecessors in the graph.

Limitations:
    - Static analysis only. Cannot resolve dynamic imports, monkey-patching,
      or runtime-generated code.
    - Call resolution is best-effort. Python's dynamic typing means many
      call targets cannot be determined without runtime information.
    - Import resolution maps to modules discovered within the repository.
      Standard library and third-party imports are not graph nodes.
"""

import logging
import sys
from pathlib import PurePosixPath

import networkx as nx

from app.models.analysis_models import (
    CallInfo,
    ClassInfo,
    FileAnalysis,
    FunctionInfo,
    ImportInfo,
    RepositoryAnalysis,
)
from app.models.graph_models import (
    ComponentNode,
    ComponentType,
    DependencyAnalysis,
    DependencyClassification,
    DependencyEdge,
    DependencyType,
    GraphStatistics,
    HighConnectivityComponent,
    ImpactResult,
    UnresolvedDependency,
)

logger = logging.getLogger(__name__)

# Top-N for highest connectivity reports
_TOP_N = 10


def _module_name_from_path(file_path: str) -> str:
    """Derive a module name from a relative file path.
    
    Examples:
        'user_service.py' -> 'user_service'
        'services/payment.py' -> 'services.payment'
        'pkg/__init__.py' -> 'pkg'
    """
    p = PurePosixPath(file_path)
    if p.stem == '__init__':
        # Package init -> use parent directory as module name
        parts = list(p.parent.parts)
        return '.'.join(parts) if parts else '__init__'
    else:
        parts = list(p.parent.parts) + [p.stem]
        return '.'.join(parts)


class DependencyGraphBuilder:
    """Builds a dependency graph from repository analysis results.
    
    Consumes a RepositoryAnalysis (produced by RepositoryScanner) and
    constructs a NetworkX directed graph with nodes for code components
    and edges for dependency relationships.
    """

    def __init__(self) -> None:
        self._graph: nx.DiGraph = nx.DiGraph()
        self._module_names: set[str] = set()
        # Mapping: module_name -> dict of exported names -> component_id
        self._module_exports: dict[str, dict[str, str]] = {}
        # Tracking unresolved dependencies
        self._unresolved: list[UnresolvedDependency] = []

    @property
    def graph(self) -> nx.DiGraph:
        """The underlying NetworkX directed graph."""
        return self._graph

    def build(self, analysis: RepositoryAnalysis) -> DependencyAnalysis:
        """Build a complete dependency graph from repository analysis.
        
        Args:
            analysis: RepositoryAnalysis from the repository scanner.
            
        Returns:
            DependencyAnalysis with nodes, edges, statistics, and unresolved deps.
        """
        self._graph = nx.DiGraph()
        self._module_names = set()
        self._module_exports = {}
        self._unresolved = []

        logger.info('Building dependency graph for: %s', analysis.repository_path)

        # Phase 1: Register all modules and their exports
        for file_analysis in analysis.files:
            if file_analysis.has_syntax_error:
                continue
            self._register_module(file_analysis)

        # Phase 2: Build CONTAINS edges
        for file_analysis in analysis.files:
            if file_analysis.has_syntax_error:
                continue
            self._build_contains_edges(file_analysis)

        # Phase 3: Build IMPORTS edges
        for file_analysis in analysis.files:
            if file_analysis.has_syntax_error:
                continue
            self._build_import_edges(file_analysis)

        # Phase 4: Build CALLS edges
        for file_analysis in analysis.files:
            if file_analysis.has_syntax_error:
                continue
            self._build_call_edges(file_analysis)

        logger.info(
            'Graph built: %d nodes, %d edges, %d unresolved',
            self._graph.number_of_nodes(),
            self._graph.number_of_edges(),
            len(self._unresolved),
        )

        return self._build_result(analysis.repository_path)

    # ------------------------------------------------------------------
    # Phase 1: Module registration
    # ------------------------------------------------------------------

    def _register_module(self, file_analysis: FileAnalysis) -> None:
        """Register a module node and index its exports."""
        module_name = _module_name_from_path(file_analysis.file_path)
        self._module_names.add(module_name)

        module_id = f'module:{module_name}'
        self._add_node(
            component_id=module_id,
            component_type=ComponentType.MODULE,
            name=module_name,
            file_path=file_analysis.file_path,
            line_number=None,
            metadata={'line_count': file_analysis.line_count},
        )

        # Index exports: name -> component_id
        exports: dict[str, str] = {}

        for func in file_analysis.functions:
            func_id = f'function:{module_name}.{func.name}'
            exports[func.name] = func_id

        for cls in file_analysis.classes:
            cls_id = f'class:{module_name}.{cls.name}'
            exports[cls.name] = cls_id
            for method in cls.methods:
                method_id = f'method:{module_name}.{cls.name}.{method.name}'
                exports[f'{cls.name}.{method.name}'] = method_id

        self._module_exports[module_name] = exports

    # ------------------------------------------------------------------
    # Phase 2: CONTAINS edges
    # ------------------------------------------------------------------

    def _build_contains_edges(self, file_analysis: FileAnalysis) -> None:
        """Build CONTAINS edges: module->function, module->class, class->method."""
        module_name = _module_name_from_path(file_analysis.file_path)
        module_id = f'module:{module_name}'

        # Module contains top-level functions
        for func in file_analysis.functions:
            func_id = f'function:{module_name}.{func.name}'
            self._add_node(
                component_id=func_id,
                component_type=ComponentType.FUNCTION,
                name=func.name,
                file_path=file_analysis.file_path,
                line_number=func.line_number,
                metadata={
                    'is_async': func.is_async,
                    'has_docstring': func.docstring is not None,
                },
            )
            self._add_edge(module_id, func_id, DependencyType.CONTAINS)

        # Module contains classes; classes contain methods
        for cls in file_analysis.classes:
            cls_id = f'class:{module_name}.{cls.name}'
            self._add_node(
                component_id=cls_id,
                component_type=ComponentType.CLASS,
                name=cls.name,
                file_path=file_analysis.file_path,
                line_number=cls.line_number,
                metadata={
                    'base_classes': ', '.join(cls.base_classes) if cls.base_classes else None,
                    'has_docstring': cls.docstring is not None,
                },
            )
            self._add_edge(module_id, cls_id, DependencyType.CONTAINS)

            for method in cls.methods:
                method_id = f'method:{module_name}.{cls.name}.{method.name}'
                self._add_node(
                    component_id=method_id,
                    component_type=ComponentType.METHOD,
                    name=method.name,
                    file_path=file_analysis.file_path,
                    line_number=method.line_number,
                    metadata={
                        'is_async': method.is_async,
                        'has_docstring': method.docstring is not None,
                        'qualified_name': f'{cls.name}.{method.name}',
                    },
                )
                self._add_edge(cls_id, method_id, DependencyType.CONTAINS)

    # ------------------------------------------------------------------
    # Phase 3: IMPORTS edges
    # ------------------------------------------------------------------

    def _build_import_edges(self, file_analysis: FileAnalysis) -> None:
        """Build IMPORTS edges between modules."""
        module_name = _module_name_from_path(file_analysis.file_path)
        module_id = f'module:{module_name}'

        seen_import_targets: set[str] = set()

        for imp in file_analysis.imports:
            target_module, classification = self._resolve_import_module(imp)
            target_id = f'module:{target_module}'
            
            if classification != DependencyClassification.FIRST_PARTY:
                if target_id not in self._graph:
                    self._add_node(
                        component_id=target_id,
                        component_type=ComponentType.MODULE,
                        name=target_module,
                        classification=classification
                    )

            # Avoid duplicate edges for the same module
            if target_id in seen_import_targets:
                continue
            seen_import_targets.add(target_id)

            if target_id != module_id:  # No self-imports
                self._add_edge(
                    module_id, target_id, DependencyType.IMPORTS,
                    metadata={'statement': imp.statement},
                )

    def _resolve_import_module(self, imp: ImportInfo) -> tuple[str, DependencyClassification]:
        """Resolve an import to a known module in the repository, standard library, or third party.
        
        Returns the module name and its classification.
        """
        candidate = imp.module

        # Direct match
        if candidate in self._module_names:
            return candidate, DependencyClassification.FIRST_PARTY

        # Try partial match for submodule imports
        parts = candidate.split('.')
        for i in range(len(parts), 0, -1):
            partial = '.'.join(parts[:i])
            if partial in self._module_names:
                return partial, DependencyClassification.FIRST_PARTY

        # Not a local module, check standard library
        base_module = candidate.split('.')[0]
        if base_module in sys.stdlib_module_names:
            return candidate, DependencyClassification.STANDARD_LIBRARY
        
        # Otherwise, third party
        return candidate, DependencyClassification.THIRD_PARTY

    # ------------------------------------------------------------------
    # Phase 4: CALLS edges
    # ------------------------------------------------------------------

    def _build_call_edges(self, file_analysis: FileAnalysis) -> None:
        """Build CALLS edges from function call information.
        
        This is the most complex resolution step because Python is
        dynamically typed. We use a best-effort strategy:
        
        1. Match against imported names from the same file.
        2. Match against module-qualified calls.
        3. Match against local definitions in the same module.
        4. Record as unresolved if no confident match is found.
        """
        module_name = _module_name_from_path(file_analysis.file_path)

        # Build an import lookup: local_name -> (source_module, imported_name)
        import_map = self._build_import_map(file_analysis.imports)

        # Build a local lookup: name -> component_id
        local_names: dict[str, str] = {}
        for func in file_analysis.functions:
            local_names[func.name] = f'function:{module_name}.{func.name}'
        for cls in file_analysis.classes:
            local_names[cls.name] = f'class:{module_name}.{cls.name}'
            for method in cls.methods:
                local_names[f'{cls.name}.{method.name}'] = (
                    f'method:{module_name}.{cls.name}.{method.name}'
                )

        for call in file_analysis.calls:
            self._resolve_call(
                call=call,
                module_name=module_name,
                import_map=import_map,
                local_names=local_names,
                file_path=file_analysis.file_path,
            )

    def _build_import_map(
        self, imports: list[ImportInfo],
    ) -> dict[str, tuple[str, str | None]]:
        """Build a mapping of locally-available names from imports.
        
        Returns:
            Dict mapping local name -> (source_module_name, original_name).
            For 'from payment_service import process_payment':
                'process_payment' -> ('payment_service', 'process_payment')
            For 'import payment_service':
                'payment_service' -> ('payment_service', None)
            For 'import payment_service as ps':
                'ps' -> ('payment_service', None)
        """
        result: dict[str, tuple[str, str | None]] = {}

        for imp in imports:
            resolved_module, classification = self._resolve_import_module(imp)
            if classification != DependencyClassification.FIRST_PARTY:
                continue  # External module

            if imp.name is not None:
                # from X import Y [as Z]
                local_name = imp.alias or imp.name
                result[local_name] = (resolved_module, imp.name)
            else:
                # import X [as Z]
                local_name = imp.alias or imp.module
                result[local_name] = (resolved_module, None)

        return result

    def _resolve_call(
        self,
        call: CallInfo,
        module_name: str,
        import_map: dict[str, tuple[str, str | None]],
        local_names: dict[str, str],
        file_path: str,
    ) -> None:
        """Attempt to resolve a call to a graph edge."""
        call_name = call.name

        # Skip common builtins and noise
        if call_name in _BUILTIN_SKIP:
            return

        # Strategy 1: Direct local name match (function call within same module)
        if call_name in local_names:
            source_id = f'module:{module_name}'
            target_id = local_names[call_name]
            if source_id != target_id:
                self._add_edge(
                    source_id, target_id, DependencyType.CALLS,
                    metadata={'line_number': call.line_number},
                )
            return

        # Strategy 2: Imported name match
        if call_name in import_map:
            source_module, original_name = import_map[call_name]
            if original_name and source_module in self._module_exports:
                exports = self._module_exports[source_module]
                if original_name in exports:
                    source_id = f'module:{module_name}'
                    target_id = exports[original_name]
                    self._add_edge(
                        source_id, target_id, DependencyType.CALLS,
                        metadata={'line_number': call.line_number},
                    )
                    return

        # Strategy 3: Dotted name resolution
        if '.' in call_name:
            resolved = self._resolve_dotted_call(call_name, import_map)
            if resolved:
                source_id = f'module:{module_name}'
                self._add_edge(
                    source_id, resolved, DependencyType.CALLS,
                    metadata={'line_number': call.line_number},
                )
                return

        # Strategy 4: Check if it's a class constructor from imports
        if call_name in import_map:
            # Name was imported but not found in exports (possibly syntax error in source)
            return

        # Unresolved -- record it
        # Skip calls that are likely instance method calls on local variables
        if not self._is_likely_instance_method(call_name):
            self._unresolved.append(UnresolvedDependency(
                source=f'module:{module_name}',
                raw_name=call_name,
                dependency_type=DependencyType.CALLS,
                reason='Cannot resolve call target statically',
                file_path=file_path,
                line_number=call.line_number,
            ))

    def _resolve_dotted_call(
        self,
        call_name: str,
        import_map: dict[str, tuple[str, str | None]],
    ) -> str | None:
        """Resolve a dotted call like 'module.function' or 'alias.method'."""
        parts = call_name.split('.')
        if len(parts) < 2:
            return None

        prefix = parts[0]

        # Check if the prefix is an imported module/alias
        if prefix in import_map:
            source_module, original_name = import_map[prefix]

            if original_name is None:
                # 'import X' -> call is X.something
                rest = '.'.join(parts[1:])
                if source_module in self._module_exports:
                    exports = self._module_exports[source_module]
                    if rest in exports:
                        return exports[rest]
                    # Try just the function name (first part after module)
                    if parts[1] in exports:
                        return exports[parts[1]]
            else:
                # 'from X import Y' and calling Y.method
                qualified = f'{original_name}.{".".join(parts[1:])}'
                if source_module in self._module_exports:
                    exports = self._module_exports[source_module]
                    if qualified in exports:
                        return exports[qualified]

        # Try direct module match
        if prefix in self._module_names:
            rest = '.'.join(parts[1:])
            if prefix in self._module_exports:
                exports = self._module_exports[prefix]
                if rest in exports:
                    return exports[rest]
                if parts[1] in exports:
                    return exports[parts[1]]

        return None

    def _is_likely_instance_method(self, call_name: str) -> bool:
        """Heuristic: skip calls that are likely instance method calls on local vars.
        
        e.g., 'self.method()', 'order.status', 'logger.info'
        These are calls on object instances, not module-level resolvable targets.
        """
        if '.' not in call_name:
            return False
        prefix = call_name.split('.')[0]
        # Common instance variable patterns
        return (
            prefix in {'self', 'cls', 'super'}
            or prefix.startswith('_')
            or (len(prefix) > 0 and prefix[0].islower())
        )

    # ------------------------------------------------------------------
    # Impact traversal
    # ------------------------------------------------------------------

    def get_direct_dependents(self, component_id: str) -> list[str]:
        """Get components that directly depend on the given component.
        
        Since edges point FROM dependent TO dependency,
        dependents are the predecessors (incoming edges) of the target node.
        
        Args:
            component_id: The component to find dependents for.
            
        Returns:
            List of component IDs that directly depend on this component.
            
        Raises:
            KeyError: If the component_id is not in the graph.
        """
        if component_id not in self._graph:
            raise KeyError(f'Component not found in graph: {component_id}')
        return sorted(self._graph.predecessors(component_id))

    def get_transitive_dependents(self, component_id: str) -> list[str]:
        """Get all components transitively dependent on the given component.
        
        Traverses the graph in reverse (following incoming edges) to find
        all components that would be affected by a change to this component.
        
        Args:
            component_id: The component to find transitive dependents for.
            
        Returns:
            List of all component IDs transitively dependent on this component.
            
        Raises:
            KeyError: If the component_id is not in the graph.
        """
        if component_id not in self._graph:
            raise KeyError(f'Component not found in graph: {component_id}')

        # BFS through predecessors
        visited: set[str] = set()
        queue = list(self._graph.predecessors(component_id))
        
        while queue:
            current = queue.pop(0)
            if current in visited or current == component_id:
                continue
            visited.add(current)
            for pred in self._graph.predecessors(current):
                if pred not in visited:
                    queue.append(pred)

        return sorted(visited)

    def get_impact(self, component_id: str) -> ImpactResult:
        """Get full impact analysis for a component.
        
        Args:
            component_id: The component to analyze.
            
        Returns:
            ImpactResult with direct and transitive dependents.
        """
        direct = self.get_direct_dependents(component_id)
        transitive = self.get_transitive_dependents(component_id)

        return ImpactResult(
            component_id=component_id,
            direct_dependents=sorted(direct),
            transitive_dependents=transitive,
            direct_count=len(direct),
            transitive_count=len(transitive),
        )

    # ------------------------------------------------------------------
    # Node/edge helpers
    # ------------------------------------------------------------------

    def _add_node(
        self,
        component_id: str,
        component_type: ComponentType,
        name: str,
        file_path: str | None = None,
        line_number: int | None = None,
        classification: DependencyClassification = DependencyClassification.FIRST_PARTY,
        metadata: dict[str, str | int | bool | None] | None = None,
    ) -> None:
        """Add a component node to the graph."""
        if component_id not in self._graph:
            node = ComponentNode(
                component_id=component_id,
                component_type=component_type,
                name=name,
                file_path=file_path,
                line_number=line_number,
                classification=classification,
                metadata=metadata or {},
            )
            self._graph.add_node(
                component_id,
                component_type=component_type.value,
                name=name,
                file_path=file_path,
                line_number=line_number,
                classification=classification.value,
                metadata=metadata or {},
            )

    def _add_edge(
        self,
        source: str,
        target: str,
        dependency_type: DependencyType,
        metadata: dict | None = None,
    ) -> None:
        """Add an edge to the graph with dependency type."""
        # Avoid duplicate edges of the same type
        if self._graph.has_edge(source, target):
            existing_type = self._graph[source][target].get('dependency_type')
            if existing_type == dependency_type.value:
                return
        self._graph.add_edge(
            source, target,
            dependency_type=dependency_type.value,
            metadata=metadata or {},
        )

    # ------------------------------------------------------------------
    # Result building
    # ------------------------------------------------------------------

    def _build_result(self, repository_path: str) -> DependencyAnalysis:
        """Build the final DependencyAnalysis result from the graph."""
        nodes = self._build_node_list()
        edges = self._build_edge_list()
        statistics = self._build_statistics(nodes, edges)
        high_conn = self._get_high_connectivity()

        # Also include high_connectivity in statistics
        statistics.highest_in_degree = sorted(
            high_conn, key=lambda x: x.in_degree, reverse=True
        )[:_TOP_N]
        statistics.highest_out_degree = sorted(
            high_conn, key=lambda x: x.out_degree, reverse=True
        )[:_TOP_N]

        return DependencyAnalysis(
            repository_path=repository_path,
            statistics=statistics,
            nodes=nodes,
            edges=edges,
            unresolved=self._unresolved,
            high_connectivity=sorted(
                high_conn, key=lambda x: x.total_degree, reverse=True
            )[:_TOP_N],
        )

    def _build_node_list(self) -> list[ComponentNode]:
        """Convert graph nodes to ComponentNode models."""
        nodes: list[ComponentNode] = []
        for node_id, attrs in self._graph.nodes(data=True):
            nodes.append(ComponentNode(
                component_id=node_id,
                component_type=ComponentType(attrs.get('component_type', 'module')),
                name=attrs.get('name', ''),
                file_path=attrs.get('file_path'),
                line_number=attrs.get('line_number'),
                metadata=attrs.get('metadata', {}),
            ))
        return sorted(nodes, key=lambda n: n.component_id)

    def _build_edge_list(self) -> list[DependencyEdge]:
        """Convert graph edges to DependencyEdge models."""
        edges: list[DependencyEdge] = []
        for source, target, attrs in self._graph.edges(data=True):
            edges.append(DependencyEdge(
                source=source,
                target=target,
                dependency_type=DependencyType(attrs.get('dependency_type', 'contains')),
                metadata=attrs.get('metadata', {}),
            ))
        return sorted(edges, key=lambda e: (e.source, e.target))

    def _build_statistics(
        self,
        nodes: list[ComponentNode],
        edges: list[DependencyEdge],
    ) -> GraphStatistics:
        """Compute aggregate statistics."""
        module_count = sum(1 for n in nodes if n.component_type == ComponentType.MODULE)
        class_count = sum(1 for n in nodes if n.component_type == ComponentType.CLASS)
        function_count = sum(1 for n in nodes if n.component_type == ComponentType.FUNCTION)
        method_count = sum(1 for n in nodes if n.component_type == ComponentType.METHOD)

        import_edges = sum(1 for e in edges if e.dependency_type == DependencyType.IMPORTS)
        call_edges = sum(1 for e in edges if e.dependency_type == DependencyType.CALLS)
        contains_edges = sum(1 for e in edges if e.dependency_type == DependencyType.CONTAINS)

        # Weakly connected components (treat as undirected for connectivity)
        if self._graph.number_of_nodes() > 0:
            connected = nx.number_weakly_connected_components(self._graph)
        else:
            connected = 0

        return GraphStatistics(
            total_nodes=len(nodes),
            total_edges=len(edges),
            module_count=module_count,
            class_count=class_count,
            function_count=function_count,
            method_count=method_count,
            import_edges=import_edges,
            call_edges=call_edges,
            contains_edges=contains_edges,
            unresolved_count=len(self._unresolved),
            connected_components=connected,
        )

    def _get_high_connectivity(self) -> list[HighConnectivityComponent]:
        """Identify components with highest connectivity."""
        result: list[HighConnectivityComponent] = []
        for node_id, attrs in self._graph.nodes(data=True):
            in_deg = self._graph.in_degree(node_id)
            out_deg = self._graph.out_degree(node_id)
            total = in_deg + out_deg
            if total > 0:
                result.append(HighConnectivityComponent(
                    component_id=node_id,
                    component_type=ComponentType(attrs.get('component_type', 'module')),
                    in_degree=in_deg,
                    out_degree=out_deg,
                    total_degree=total,
                ))
        return result


# Common builtins to skip during call resolution
_BUILTIN_SKIP = frozenset({
    'print', 'len', 'range', 'str', 'int', 'float', 'bool', 'list', 'dict',
    'set', 'tuple', 'type', 'isinstance', 'issubclass', 'hasattr', 'getattr',
    'setattr', 'delattr', 'super', 'property', 'classmethod', 'staticmethod',
    'enumerate', 'zip', 'map', 'filter', 'sorted', 'reversed', 'any', 'all',
    'min', 'max', 'sum', 'abs', 'round', 'hash', 'id', 'repr', 'format',
    'open', 'input', 'vars', 'dir', 'help', 'iter', 'next', 'callable',
    'object', 'Exception', 'ValueError', 'TypeError', 'KeyError',
    'AttributeError', 'RuntimeError', 'StopIteration', 'IndexError',
    'NotImplementedError', 'ImportError', 'OSError', 'FileNotFoundError',
    'PermissionError', 'IOError',
})
