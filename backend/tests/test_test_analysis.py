"""Tests for Milestone 5 — Test Impact Analysis & Test Selection.

All tests use temporary local repositories. No internet or external
resources required. ScopeGuard never executes tests from analyzed repos.
"""

import textwrap
from pathlib import Path

import git
import pytest

from app.analyzers.test_analyzer import TestAnalyzer
from app.analyzers.test_impact_analyzer import TestImpactAnalyzer
from app.models.test_models import TestPriority


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

def _init_repo(path: Path) -> git.Repo:
    repo = git.Repo.init(str(path))
    repo.config_writer().set_value('user', 'name', 'Test').release()
    repo.config_writer().set_value('user', 'email', 'test@test.com').release()
    return repo


def _commit(repo: git.Repo, message: str):
    repo.git.add(A=True)
    return repo.index.commit(message)


# ---------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------

@pytest.fixture
def test_analyzer():
    return TestAnalyzer()


@pytest.fixture
def simple_repo(tmp_path):
    """Repo with app code and test files for discovery testing."""
    repo = _init_repo(tmp_path)

    (tmp_path / 'service.py').write_text(textwrap.dedent('''\
        def process(data):
            return data

        def validate(item):
            return item is not None
    '''))

    (tmp_path / 'helper.py').write_text(textwrap.dedent('''\
        def do_work():
            return 1
    '''))

    tests_dir = tmp_path / 'tests'
    tests_dir.mkdir()
    (tests_dir / '__init__.py').write_text('')

    (tests_dir / 'test_service.py').write_text(textwrap.dedent('''\
        from service import process, validate

        def test_process():
            assert process("x") == "x"

        def test_validate():
            assert validate("x") is True
    '''))

    (tests_dir / 'test_helper.py').write_text(textwrap.dedent('''\
        from helper import do_work

        def test_do_work():
            assert do_work() == 1
    '''))

    _commit(repo, 'Initial')
    return tmp_path


@pytest.fixture
def impact_repo(tmp_path):
    """Repo with dependency chain for impact testing."""
    repo = _init_repo(tmp_path)

    (tmp_path / 'core.py').write_text(textwrap.dedent('''\
        def compute():
            return 42
    '''))

    (tmp_path / 'service.py').write_text(textwrap.dedent('''\
        from core import compute

        def serve():
            return compute()
    '''))

    (tmp_path / 'api.py').write_text(textwrap.dedent('''\
        from service import serve

        def handle():
            return serve()
    '''))

    tests_dir = tmp_path / 'tests'
    tests_dir.mkdir()
    (tests_dir / '__init__.py').write_text('')

    (tests_dir / 'test_core.py').write_text(textwrap.dedent('''\
        from core import compute

        def test_compute():
            assert compute() == 42
    '''))

    (tests_dir / 'test_service.py').write_text(textwrap.dedent('''\
        from service import serve

        def test_serve():
            assert serve() == 42
    '''))

    (tests_dir / 'test_api.py').write_text(textwrap.dedent('''\
        from api import handle

        def test_handle():
            assert handle() == 42
    '''))

    (tests_dir / 'test_unrelated.py').write_text(textwrap.dedent('''\
        def test_standalone():
            assert True
    '''))

    _commit(repo, 'Initial')

    # Commit 2: modify core.compute
    (tmp_path / 'core.py').write_text(textwrap.dedent('''\
        def compute():
            return 99
    '''))
    _commit(repo, 'Change compute return value')

    return tmp_path


@pytest.fixture
def class_test_repo(tmp_path):
    """Repo with class-style tests."""
    repo = _init_repo(tmp_path)

    (tmp_path / 'engine.py').write_text(textwrap.dedent('''\
        class Engine:
            def run(self):
                return "running"
    '''))

    tests_dir = tmp_path / 'tests'
    tests_dir.mkdir()
    (tests_dir / '__init__.py').write_text('')

    (tests_dir / 'test_engine.py').write_text(textwrap.dedent('''\
        from engine import Engine

        class TestEngine:
            def test_run(self):
                e = Engine()
                assert e.run() == "running"

            def test_engine_exists(self):
                assert Engine is not None
    '''))

    _commit(repo, 'Initial')

    (tmp_path / 'engine.py').write_text(textwrap.dedent('''\
        class Engine:
            def run(self, turbo=False):
                if turbo:
                    return "turbo"
                return "running"
    '''))
    _commit(repo, 'Add turbo mode')

    return tmp_path


# ---------------------------------------------------------------
# Test Discovery
# ---------------------------------------------------------------

class TestDiscovery:
    def test_discovers_test_files(self, test_analyzer, simple_repo):
        tests = test_analyzer.discover_tests(simple_repo)
        test_files = {t.test_file for t in tests}
        assert any('test_service' in f for f in test_files)
        assert any('test_helper' in f for f in test_files)

    def test_discovers_test_functions(self, test_analyzer, simple_repo):
        tests = test_analyzer.discover_tests(simple_repo)
        names = {t.test_name for t in tests}
        assert 'test_process' in names
        assert 'test_validate' in names
        assert 'test_do_work' in names

    def test_empty_repo(self, test_analyzer, tmp_path):
        _init_repo(tmp_path)
        (tmp_path / 'app.py').write_text('x = 1\n')
        tests = test_analyzer.discover_tests(tmp_path)
        assert len(tests) == 0

    def test_non_test_files_ignored(self, test_analyzer, simple_repo):
        tests = test_analyzer.discover_tests(simple_repo)
        test_files = {t.test_file for t in tests}
        assert not any('service.py' == f for f in test_files)
        assert not any('helper.py' == f for f in test_files)

    def test_test_id_format(self, test_analyzer, simple_repo):
        tests = test_analyzer.discover_tests(simple_repo)
        t = next(t for t in tests if t.test_name == 'test_process')
        assert '::' in t.test_id
        assert 'test_service' in t.test_id

    def test_line_numbers(self, test_analyzer, simple_repo):
        tests = test_analyzer.discover_tests(simple_repo)
        for t in tests:
            assert t.line_number > 0

    def test_class_tests_discovered(self, test_analyzer, class_test_repo):
        tests = test_analyzer.discover_tests(class_test_repo)
        names = {t.test_name for t in tests}
        assert 'test_run' in names
        assert 'test_engine_exists' in names

    def test_class_test_has_class_name(self, test_analyzer, class_test_repo):
        tests = test_analyzer.discover_tests(class_test_repo)
        t = next(t for t in tests if t.test_name == 'test_run')
        assert t.class_name == 'TestEngine'


# ---------------------------------------------------------------
# Component Mapping
# ---------------------------------------------------------------

class TestMapping:
    def test_maps_imports(self, test_analyzer, simple_repo):
        tests = test_analyzer.discover_tests(simple_repo)
        mappings = test_analyzer.build_mappings(tests, simple_repo)
        svc_map = next(
            m for m in mappings
            if 'test_service' in m.test_id and 'test_process' in m.test_id
        )
        assert 'service' in svc_map.referenced_modules

    def test_maps_with_graph_ids(self, test_analyzer, simple_repo):
        tests = test_analyzer.discover_tests(simple_repo)
        known = {'module:service', 'function:service.process',
                 'function:service.validate', 'module:helper',
                 'function:helper.do_work'}
        mappings = test_analyzer.build_mappings(tests, simple_repo, known)
        svc_map = next(
            m for m in mappings
            if 'test_service' in m.test_id and 'test_process' in m.test_id
        )
        assert 'function:service.process' in svc_map.referenced_component_ids

    def test_no_duplicate_mappings(self, test_analyzer, simple_repo):
        tests = test_analyzer.discover_tests(simple_repo)
        mappings = test_analyzer.build_mappings(tests, simple_repo)
        ids = [m.test_id for m in mappings]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------
# Test Impact Analysis
# ---------------------------------------------------------------

class TestImpactSelection:
    def test_direct_reference_is_high(self, impact_repo):
        analyzer = TestImpactAnalyzer()
        result = analyzer.analyze_commit_tests(impact_repo, 'HEAD')
        sel = result.test_selection
        high_names = {t.test.test_name for t in sel.high_priority}
        assert 'test_compute' in high_names

    def test_dependency_is_medium(self, impact_repo):
        analyzer = TestImpactAnalyzer()
        result = analyzer.analyze_commit_tests(impact_repo, 'HEAD')
        sel = result.test_selection
        medium_names = {t.test.test_name for t in sel.medium_priority}
        # test_serve references service which depends on core
        assert 'test_serve' in medium_names

    def test_transitive_is_low(self, impact_repo):
        analyzer = TestImpactAnalyzer()
        result = analyzer.analyze_commit_tests(impact_repo, 'HEAD')
        sel = result.test_selection
        low_names = {t.test.test_name for t in sel.low_priority}
        # test_handle references api which transitively depends on core
        assert 'test_handle' in low_names

    def test_unrelated_is_skipped(self, impact_repo):
        analyzer = TestImpactAnalyzer()
        result = analyzer.analyze_commit_tests(impact_repo, 'HEAD')
        sel = result.test_selection
        all_selected = (
            {t.test.test_name for t in sel.high_priority}
            | {t.test.test_name for t in sel.medium_priority}
            | {t.test.test_name for t in sel.low_priority}
        )
        assert 'test_standalone' not in all_selected

    def test_skipped_count(self, impact_repo):
        analyzer = TestImpactAnalyzer()
        result = analyzer.analyze_commit_tests(impact_repo, 'HEAD')
        sel = result.test_selection
        assert sel.skipped_tests == sel.total_tests - sel.selected_tests

    def test_selection_percentage(self, impact_repo):
        analyzer = TestImpactAnalyzer()
        result = analyzer.analyze_commit_tests(impact_repo, 'HEAD')
        sel = result.test_selection
        expected_pct = round(sel.selected_tests / sel.total_tests * 100, 1)
        assert sel.selection_percentage == expected_pct

    def test_reasons_present(self, impact_repo):
        analyzer = TestImpactAnalyzer()
        result = analyzer.analyze_commit_tests(impact_repo, 'HEAD')
        sel = result.test_selection
        for t in sel.high_priority:
            assert t.reason
            assert 'changed' in t.reason.lower() or 'direct' in t.reason.lower()

    def test_no_duplicates(self, impact_repo):
        analyzer = TestImpactAnalyzer()
        result = analyzer.analyze_commit_tests(impact_repo, 'HEAD')
        sel = result.test_selection
        all_ids = (
            [t.test.test_id for t in sel.high_priority]
            + [t.test.test_id for t in sel.medium_priority]
            + [t.test.test_id for t in sel.low_priority]
        )
        assert len(all_ids) == len(set(all_ids))

    def test_deterministic(self, impact_repo):
        analyzer = TestImpactAnalyzer()
        r1 = analyzer.analyze_commit_tests(impact_repo, 'HEAD')
        r2 = analyzer.analyze_commit_tests(impact_repo, 'HEAD')
        assert r1.test_selection.selected_tests == r2.test_selection.selected_tests
        assert r1.test_selection.selection_percentage == r2.test_selection.selection_percentage

    def test_class_tests_impact(self, class_test_repo):
        analyzer = TestImpactAnalyzer()
        result = analyzer.analyze_commit_tests(class_test_repo, 'HEAD')
        sel = result.test_selection
        selected = (
            {t.test.test_name for t in sel.high_priority}
            | {t.test.test_name for t in sel.medium_priority}
            | {t.test.test_name for t in sel.low_priority}
        )
        assert 'test_run' in selected or 'test_engine_exists' in selected


# ---------------------------------------------------------------
# API Endpoint
# ---------------------------------------------------------------

class TestTestEndpoint:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_endpoint_success(self, client, impact_repo):
        r = client.post('/api/analyze/commit/tests', json={
            'path': str(impact_repo),
            'commit': 'HEAD',
        })
        assert r.status_code == 200
        data = r.json()
        assert 'test_selection' in data
        sel = data['test_selection']
        assert 'total_tests' in sel
        assert 'selected_tests' in sel
        assert 'skipped_tests' in sel
        assert 'selection_percentage' in sel
        assert 'high_priority' in sel
        assert 'medium_priority' in sel
        assert 'low_priority' in sel

    def test_endpoint_invalid_path(self, client):
        r = client.post('/api/analyze/commit/tests', json={
            'path': '/nonexistent',
            'commit': 'HEAD',
        })
        assert r.status_code in (400, 404)

    def test_endpoint_invalid_commit(self, client, impact_repo):
        r = client.post('/api/analyze/commit/tests', json={
            'path': str(impact_repo),
            'commit': 'deadbeef' * 5,
        })
        assert r.status_code == 400

    def test_existing_commit_endpoint_unchanged(self, client, impact_repo):
        """M3 endpoint must still work without test_selection."""
        r = client.post('/api/analyze/commit', json={
            'path': str(impact_repo),
            'commit': 'HEAD',
        })
        assert r.status_code == 200
        assert 'test_selection' not in r.json()

    def test_existing_risk_endpoint_unchanged(self, client, impact_repo):
        """M4 endpoint must still work without test_selection."""
        r = client.post('/api/analyze/commit/risk', json={
            'path': str(impact_repo),
            'commit': 'HEAD',
        })
        assert r.status_code == 200
        assert 'risk' in r.json()
        assert 'test_selection' not in r.json()
