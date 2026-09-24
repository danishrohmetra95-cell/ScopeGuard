"""Tests for the dependency graph engine."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from app.analyzers.dependency_graph import DependencyGraphBuilder, _module_name_from_path
from app.analyzers.repository_scanner import RepositoryScanner
from app.models.analysis_models import (
    CallInfo,
    ClassInfo,
    FileAnalysis,
    FunctionInfo,
    ImportInfo,
    RepositoryAnalysis,
    RepositorySummary,
)
from app.models.graph_models import (
    ComponentType,
    DependencyType,
)


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

def _make_analysis(files: list[FileAnalysis], repo_path: str = '/repo') -> RepositoryAnalysis:
    """Helper to build a RepositoryAnalysis from file analyses."""
    return RepositoryAnalysis(
        repository_path=repo_path,
        files=files,
        summary=RepositorySummary(total_files=len(files)),
    )


def _make_file(
    file_path: str,
    functions: list[FunctionInfo] | None = None,
    classes: list[ClassInfo] | None = None,
    imports: list[ImportInfo] | None = None,
    calls: list[CallInfo] | None = None,
) -> FileAnalysis:
    """Helper to create a FileAnalysis with minimal boilerplate."""
    return FileAnalysis(
        file_path=file_path,
        absolute_path=f'/repo/{file_path}',
        line_count=10,
        functions=functions or [],
        classes=classes or [],
        imports=imports or [],
        calls=calls or [],
    )


# ---------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------

@pytest.fixture
def builder():
    """Fresh DependencyGraphBuilder."""
    return DependencyGraphBuilder()


@pytest.fixture
def simple_repo() -> RepositoryAnalysis:
    """A simple repo with two modules where A imports and calls B."""
    file_a = _make_file(
        'module_a.py',
        functions=[
            FunctionInfo(name='do_work', qualified_name='do_work', line_number=5),
        ],
        imports=[
            ImportInfo(module='module_b', name='helper', line_number=1,
                       statement='from module_b import helper'),
        ],
        calls=[
            CallInfo(name='helper', line_number=6, is_method_call=False),
        ],
    )
    file_b = _make_file(
        'module_b.py',
        functions=[
            FunctionInfo(name='helper', qualified_name='helper', line_number=3),
        ],
    )
    return _make_analysis([file_a, file_b])


@pytest.fixture
def class_repo() -> RepositoryAnalysis:
    """A repo with a class and methods."""
    file_a = _make_file(
        'service.py',
        classes=[
            ClassInfo(
                name='MyService',
                line_number=5,
                base_classes=['BaseService'],
                methods=[
                    FunctionInfo(
                        name='process',
                        qualified_name='MyService.process',
                        line_number=8,
                        is_method=True,
                    ),
                    FunctionInfo(
                        name='validate',
                        qualified_name='MyService.validate',
                        line_number=15,
                        is_method=True,
                    ),
                ],
            ),
        ],
        functions=[
            FunctionInfo(name='create_service', qualified_name='create_service', line_number=25),
        ],
    )
    return _make_analysis([file_a])


@pytest.fixture
def chain_repo() -> RepositoryAnalysis:
    """A -> B -> C dependency chain for transitive testing."""
    file_a = _make_file(
        'a.py',
        functions=[FunctionInfo(name='func_a', qualified_name='func_a', line_number=3)],
        imports=[ImportInfo(module='b', name='func_b', line_number=1,
                            statement='from b import func_b')],
        calls=[CallInfo(name='func_b', line_number=4, is_method_call=False)],
    )
    file_b = _make_file(
        'b.py',
        functions=[FunctionInfo(name='func_b', qualified_name='func_b', line_number=3)],
        imports=[ImportInfo(module='c', name='func_c', line_number=1,
                            statement='from c import func_c')],
        calls=[CallInfo(name='func_c', line_number=4, is_method_call=False)],
    )
    file_c = _make_file(
        'c.py',
        functions=[FunctionInfo(name='func_c', qualified_name='func_c', line_number=3)],
    )
    return _make_analysis([file_a, file_b, file_c])


@pytest.fixture
def alias_repo() -> RepositoryAnalysis:
    """A repo with aliased imports."""
    file_a = _make_file(
        'consumer.py',
        functions=[FunctionInfo(name='run', qualified_name='run', line_number=5)],
        imports=[
            ImportInfo(module='provider', name='create', alias='make', line_number=1,
                       statement='from provider import create as make'),
        ],
        calls=[
            CallInfo(name='make', line_number=6, is_method_call=False),
        ],
    )
    file_b = _make_file(
        'provider.py',
        functions=[FunctionInfo(name='create', qualified_name='create', line_number=3)],
    )
    return _make_analysis([file_a, file_b])


# ---------------------------------------------------------------
# Module name derivation
# ---------------------------------------------------------------

class TestModuleNameFromPath:
    def test_simple_file(self):
        assert _module_name_from_path('service.py') == 'service'

    def test_nested_file(self):
        assert _module_name_from_path('services/payment.py') == 'services.payment'

    def test_init_file(self):
        assert _module_name_from_path('pkg/__init__.py') == 'pkg'

    def test_deeply_nested(self):
        assert _module_name_from_path('a/b/c/module.py') == 'a.b.c.module'


# ---------------------------------------------------------------
# Module nodes
# ---------------------------------------------------------------

class TestModuleNodes:
    def test_creates_module_nodes(self, builder, simple_repo):
        result = builder.build(simple_repo)
        module_nodes = [n for n in result.nodes if n.component_type == ComponentType.MODULE]
        module_ids = [n.component_id for n in module_nodes]
        assert 'module:module_a' in module_ids
        assert 'module:module_b' in module_ids

    def test_module_node_has_file_path(self, builder, simple_repo):
        result = builder.build(simple_repo)
        node = next(n for n in result.nodes if n.component_id == 'module:module_a')
        assert node.file_path == 'module_a.py'


# ---------------------------------------------------------------
# Class nodes
# ---------------------------------------------------------------

class TestClassNodes:
    def test_creates_class_nodes(self, builder, class_repo):
        result = builder.build(class_repo)
        class_nodes = [n for n in result.nodes if n.component_type == ComponentType.CLASS]
        assert len(class_nodes) == 1
        assert class_nodes[0].component_id == 'class:service.MyService'

    def test_class_has_line_number(self, builder, class_repo):
        result = builder.build(class_repo)
        cls = next(n for n in result.nodes if n.component_type == ComponentType.CLASS)
        assert cls.line_number == 5


# ---------------------------------------------------------------
# Function nodes
# ---------------------------------------------------------------

class TestFunctionNodes:
    def test_creates_function_nodes(self, builder, simple_repo):
        result = builder.build(simple_repo)
        func_nodes = [n for n in result.nodes if n.component_type == ComponentType.FUNCTION]
        func_ids = [n.component_id for n in func_nodes]
        assert 'function:module_a.do_work' in func_ids
        assert 'function:module_b.helper' in func_ids

    def test_creates_method_nodes(self, builder, class_repo):
        result = builder.build(class_repo)
        method_nodes = [n for n in result.nodes if n.component_type == ComponentType.METHOD]
        method_ids = [n.component_id for n in method_nodes]
        assert 'method:service.MyService.process' in method_ids
        assert 'method:service.MyService.validate' in method_ids


# ---------------------------------------------------------------
# CONTAINS edges
# ---------------------------------------------------------------

class TestContainsEdges:
    def test_module_contains_function(self, builder, simple_repo):
        result = builder.build(simple_repo)
        contains = [(e.source, e.target) for e in result.edges
                     if e.dependency_type == DependencyType.CONTAINS]
        assert ('module:module_a', 'function:module_a.do_work') in contains

    def test_module_contains_class(self, builder, class_repo):
        result = builder.build(class_repo)
        contains = [(e.source, e.target) for e in result.edges
                     if e.dependency_type == DependencyType.CONTAINS]
        assert ('module:service', 'class:service.MyService') in contains

    def test_class_contains_method(self, builder, class_repo):
        result = builder.build(class_repo)
        contains = [(e.source, e.target) for e in result.edges
                     if e.dependency_type == DependencyType.CONTAINS]
        assert ('class:service.MyService', 'method:service.MyService.process') in contains

    def test_module_contains_top_level_function(self, builder, class_repo):
        result = builder.build(class_repo)
        contains = [(e.source, e.target) for e in result.edges
                     if e.dependency_type == DependencyType.CONTAINS]
        assert ('module:service', 'function:service.create_service') in contains


# ---------------------------------------------------------------
# IMPORTS edges
# ---------------------------------------------------------------

class TestImportEdges:
    def test_creates_import_edges(self, builder, simple_repo):
        result = builder.build(simple_repo)
        imports = [(e.source, e.target) for e in result.edges
                    if e.dependency_type == DependencyType.IMPORTS]
        assert ('module:module_a', 'module:module_b') in imports

    def test_no_self_import_edges(self, builder):
        file_a = _make_file(
            'self_ref.py',
            imports=[
                ImportInfo(module='self_ref', name='something', line_number=1,
                           statement='from self_ref import something'),
            ],
        )
        result = builder.build(_make_analysis([file_a]))
        import_edges = [e for e in result.edges if e.dependency_type == DependencyType.IMPORTS]
        assert not any(e.source == e.target for e in import_edges)

    def test_external_imports_not_in_graph(self, builder, simple_repo):
        result = builder.build(simple_repo)
        node_ids = [n.component_id for n in result.nodes]
        assert all(
            n.startswith(('module:', 'function:', 'class:', 'method:'))
            for n in node_ids
        )


# ---------------------------------------------------------------
# CALLS edges
# ---------------------------------------------------------------

class TestCallEdges:
    def test_creates_call_edges(self, builder, simple_repo):
        result = builder.build(simple_repo)
        calls = [(e.source, e.target) for e in result.edges
                  if e.dependency_type == DependencyType.CALLS]
        assert ('module:module_a', 'function:module_b.helper') in calls

    def test_local_calls(self, builder):
        file_a = _make_file(
            'local.py',
            functions=[
                FunctionInfo(name='caller', qualified_name='caller', line_number=3),
                FunctionInfo(name='callee', qualified_name='callee', line_number=8),
            ],
            calls=[
                CallInfo(name='callee', line_number=5, is_method_call=False),
            ],
        )
        result = builder.build(_make_analysis([file_a]))
        calls = [(e.source, e.target) for e in result.edges
                  if e.dependency_type == DependencyType.CALLS]
        assert ('module:local', 'function:local.callee') in calls


# ---------------------------------------------------------------
# Aliases
# ---------------------------------------------------------------

class TestAliases:
    def test_aliased_import_call_resolved(self, builder, alias_repo):
        result = builder.build(alias_repo)
        calls = [(e.source, e.target) for e in result.edges
                  if e.dependency_type == DependencyType.CALLS]
        assert ('module:consumer', 'function:provider.create') in calls

    def test_aliased_import_edge(self, builder, alias_repo):
        result = builder.build(alias_repo)
        imports = [(e.source, e.target) for e in result.edges
                    if e.dependency_type == DependencyType.IMPORTS]
        assert ('module:consumer', 'module:provider') in imports


# ---------------------------------------------------------------
# Unresolved calls
# ---------------------------------------------------------------

class TestUnresolvedCalls:
    def test_unresolved_calls_recorded(self, builder):
        file_a = _make_file(
            'caller.py',
            functions=[
                FunctionInfo(name='run', qualified_name='run', line_number=3),
            ],
            calls=[
                CallInfo(name='unknown_function', line_number=5, is_method_call=False),
            ],
        )
        result = builder.build(_make_analysis([file_a]))
        assert len(result.unresolved) > 0
        assert any(u.raw_name == 'unknown_function' for u in result.unresolved)

    def test_builtins_not_unresolved(self, builder):
        file_a = _make_file(
            'builtins_test.py',
            calls=[
                CallInfo(name='print', line_number=1, is_method_call=False),
                CallInfo(name='len', line_number=2, is_method_call=False),
            ],
        )
        result = builder.build(_make_analysis([file_a]))
        unresolved_names = [u.raw_name for u in result.unresolved]
        assert 'print' not in unresolved_names
        assert 'len' not in unresolved_names


# ---------------------------------------------------------------
# Direct dependents
# ---------------------------------------------------------------

class TestDirectDependents:
    def test_direct_dependents_via_import(self, builder, simple_repo):
        builder.build(simple_repo)
        deps = builder.get_direct_dependents('module:module_b')
        assert 'module:module_a' in deps

    def test_direct_dependents_via_call(self, builder, simple_repo):
        builder.build(simple_repo)
        deps = builder.get_direct_dependents('function:module_b.helper')
        assert 'module:module_a' in deps

    def test_direct_dependents_contains(self, builder, class_repo):
        builder.build(class_repo)
        deps = builder.get_direct_dependents('class:service.MyService')
        assert 'module:service' in deps

    def test_unknown_component_raises(self, builder, simple_repo):
        builder.build(simple_repo)
        with pytest.raises(KeyError):
            builder.get_direct_dependents('module:nonexistent')


# ---------------------------------------------------------------
# Transitive dependents
# ---------------------------------------------------------------

class TestTransitiveDependents:
    def test_transitive_chain(self, builder, chain_repo):
        """A->B->C: changing func_c should transitively affect module:b and module:a."""
        builder.build(chain_repo)
        transitive = builder.get_transitive_dependents('function:c.func_c')
        assert 'module:b' in transitive
        assert 'module:a' in transitive

    def test_transitive_no_self_inclusion(self, builder, chain_repo):
        builder.build(chain_repo)
        transitive = builder.get_transitive_dependents('function:c.func_c')
        assert 'function:c.func_c' not in transitive

    def test_transitive_unknown_raises(self, builder, chain_repo):
        builder.build(chain_repo)
        with pytest.raises(KeyError):
            builder.get_transitive_dependents('module:nonexistent')

    def test_leaf_node_dependents(self, builder, chain_repo):
        """func_a is contained by module:a, so module:a is a predecessor."""
        builder.build(chain_repo)
        deps = builder.get_direct_dependents('function:a.func_a')
        assert 'module:a' in deps


# ---------------------------------------------------------------
# Graph statistics
# ---------------------------------------------------------------

class TestGraphStatistics:
    def test_node_counts(self, builder, simple_repo):
        result = builder.build(simple_repo)
        stats = result.statistics
        assert stats.module_count == 2
        assert stats.function_count == 2
        assert stats.total_nodes == 4  # 2 modules + 2 functions

    def test_edge_counts(self, builder, simple_repo):
        result = builder.build(simple_repo)
        stats = result.statistics
        assert stats.import_edges >= 1
        assert stats.contains_edges >= 2
        assert stats.call_edges >= 1

    def test_unresolved_count(self, builder):
        file_a = _make_file(
            'test.py',
            calls=[CallInfo(name='mystery', line_number=1, is_method_call=False)],
        )
        result = builder.build(_make_analysis([file_a]))
        assert result.statistics.unresolved_count > 0

    def test_connected_components(self, builder):
        """Two isolated modules should be two connected components."""
        file_a = _make_file('isolated_a.py', functions=[
            FunctionInfo(name='fa', qualified_name='fa', line_number=1),
        ])
        file_b = _make_file('isolated_b.py', functions=[
            FunctionInfo(name='fb', qualified_name='fb', line_number=1),
        ])
        result = builder.build(_make_analysis([file_a, file_b]))
        assert result.statistics.connected_components == 2

    def test_high_connectivity(self, builder, chain_repo):
        result = builder.build(chain_repo)
        assert len(result.statistics.highest_in_degree) > 0


# ---------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------

class TestEdgeCases:
    def test_empty_repo(self, builder):
        result = builder.build(_make_analysis([]))
        assert result.statistics.total_nodes == 0
        assert result.statistics.total_edges == 0

    def test_file_with_syntax_error_skipped(self, builder):
        file_ok = _make_file('ok.py', functions=[
            FunctionInfo(name='good', qualified_name='good', line_number=1),
        ])
        file_bad = FileAnalysis(
            file_path='bad.py',
            absolute_path='/repo/bad.py',
            has_syntax_error=True,
            syntax_error_message='invalid syntax',
        )
        result = builder.build(_make_analysis([file_ok, file_bad]))
        node_ids = [n.component_id for n in result.nodes]
        assert 'module:ok' in node_ids
        assert 'module:bad' not in node_ids

    def test_init_file_module_name(self, builder):
        file_init = _make_file('pkg/__init__.py', functions=[
            FunctionInfo(name='init_func', qualified_name='init_func', line_number=1),
        ])
        result = builder.build(_make_analysis([file_init]))
        node_ids = [n.component_id for n in result.nodes]
        assert 'module:pkg' in node_ids
        assert 'function:pkg.init_func' in node_ids


# ---------------------------------------------------------------
# Sample repository integration
# ---------------------------------------------------------------

class TestSampleRepository:
    """Integration tests using the actual sample-repository."""

    @pytest.fixture
    def sample_analysis(self) -> RepositoryAnalysis:
        scanner = RepositoryScanner()
        sample_path = Path(__file__).resolve().parent.parent.parent / 'sample-repository'
        return scanner.scan(sample_path)

    def test_sample_repo_graph_builds(self, sample_analysis):
        builder = DependencyGraphBuilder()
        result = builder.build(sample_analysis)
        assert result.statistics.total_nodes > 0
        assert result.statistics.total_edges > 0

    def test_sample_repo_has_modules(self, sample_analysis):
        builder = DependencyGraphBuilder()
        result = builder.build(sample_analysis)
        module_ids = [
            n.component_id for n in result.nodes
            if n.component_type == ComponentType.MODULE
        ]
        assert 'module:order_service' in module_ids
        assert 'module:payment_service' in module_ids
        assert 'module:user_service' in module_ids
        assert 'module:notification_service' in module_ids

    def test_sample_repo_import_edges(self, sample_analysis):
        builder = DependencyGraphBuilder()
        result = builder.build(sample_analysis)
        import_edges = [
            (e.source, e.target) for e in result.edges
            if e.dependency_type == DependencyType.IMPORTS
        ]
        assert ('module:order_service', 'module:payment_service') in import_edges
        assert ('module:order_service', 'module:notification_service') in import_edges

    def test_sample_repo_call_edges(self, sample_analysis):
        builder = DependencyGraphBuilder()
        result = builder.build(sample_analysis)
        call_edges = [
            (e.source, e.target) for e in result.edges
            if e.dependency_type == DependencyType.CALLS
        ]
        assert ('module:order_service', 'function:payment_service.process_payment') in call_edges

    def test_sample_repo_contains_edges(self, sample_analysis):
        builder = DependencyGraphBuilder()
        result = builder.build(sample_analysis)
        contains_edges = [
            (e.source, e.target) for e in result.edges
            if e.dependency_type == DependencyType.CONTAINS
        ]
        assert ('module:payment_service', 'function:payment_service.process_payment') in contains_edges

    def test_sample_repo_has_api_module(self, sample_analysis):
        builder = DependencyGraphBuilder()
        result = builder.build(sample_analysis)
        module_ids = [n.component_id for n in result.nodes
                      if n.component_type == ComponentType.MODULE]
        assert 'module:api' in module_ids

    def test_sample_repo_graph_statistics(self, sample_analysis):
        builder = DependencyGraphBuilder()
        result = builder.build(sample_analysis)
        stats = result.statistics
        assert stats.module_count >= 7
        assert stats.function_count > 10
        assert stats.import_edges > 5
        assert stats.call_edges > 0

    def test_sample_repo_impact_traversal(self, sample_analysis):
        builder = DependencyGraphBuilder()
        builder.build(sample_analysis)
        impact = builder.get_impact('function:notification_service.send_notification')
        assert impact.direct_count > 0
        assert impact.transitive_count >= impact.direct_count


# ---------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------

class TestDependencyEndpoints:
    """Tests for the dependency analysis API endpoints."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    @pytest.fixture
    def sample_repo_path(self) -> str:
        return str(Path(__file__).resolve().parent.parent.parent / 'sample-repository')

    def test_dependencies_endpoint_success(self, client, sample_repo_path):
        response = client.post(
            '/api/analyze/dependencies',
            json={'path': sample_repo_path},
        )
        assert response.status_code == 200
        data = response.json()
        assert 'statistics' in data
        assert 'nodes' in data
        assert 'edges' in data
        assert data['statistics']['total_nodes'] > 0

    def test_dependencies_endpoint_not_found(self, client):
        response = client.post(
            '/api/analyze/dependencies',
            json={'path': '/nonexistent/repo/path'},
        )
        assert response.status_code == 404

    def test_impact_endpoint_success(self, client, sample_repo_path):
        response = client.get(
            '/api/analyze/dependencies/function:notification_service.send_notification/impact',
            params={'repository_path': sample_repo_path},
        )
        assert response.status_code == 200
        data = response.json()
        assert 'direct_dependents' in data
        assert 'transitive_dependents' in data
        assert data['direct_count'] > 0

    def test_impact_endpoint_component_not_found(self, client, sample_repo_path):
        response = client.get(
            '/api/analyze/dependencies/module:nonexistent/impact',
            params={'repository_path': sample_repo_path},
        )
        assert response.status_code == 404
