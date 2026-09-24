"""Tests for Milestone 3 — Git diff and change impact analysis.

All tests use temporary local Git repositories created via pytest fixtures.
No internet or external repositories required.
"""

import textwrap
from pathlib import Path

import git
import pytest

from app.analyzers.change_detector import ChangeDetector
from app.analyzers.impact_analyzer import ImpactAnalyzer
from app.models.change_models import (
    ChangeType,
    ComponentChangeType,
)
from app.services.git_service import GitService


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

def _init_repo(path: Path) -> git.Repo:
    """Initialise a git repo with a dummy user config."""
    repo = git.Repo.init(str(path))
    repo.config_writer().set_value('user', 'name', 'Test').release()
    repo.config_writer().set_value('user', 'email', 'test@test.com').release()
    return repo


def _commit(repo: git.Repo, message: str, paths: list[str] | None = None):
    """Stage files and commit."""
    if paths:
        repo.index.add(paths)
    else:
        repo.git.add(A=True)
    return repo.index.commit(message)


# ---------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------

@pytest.fixture
def git_service():
    return GitService()


@pytest.fixture
def change_detector():
    return ChangeDetector()


@pytest.fixture
def basic_repo(tmp_path):
    """Two-commit repo: initial file → modify one function, add another."""
    repo = _init_repo(tmp_path)

    (tmp_path / 'service.py').write_text(textwrap.dedent('''\
        """Service module."""

        def process(data):
            """Process data."""
            return data

        def validate(item):
            """Validate an item."""
            return item is not None
    '''))
    _commit(repo, 'Initial commit')

    (tmp_path / 'service.py').write_text(textwrap.dedent('''\
        """Service module."""

        def process(data):
            """Process data with extra validation."""
            if not data:
                raise ValueError("empty")
            return data.strip()

        def validate(item):
            """Validate an item."""
            return item is not None

        def transform(data):
            """New function."""
            return data.upper()
    '''))
    _commit(repo, 'Modify process, add transform')

    return tmp_path


@pytest.fixture
def delete_repo(tmp_path):
    """Two-commit repo: initial → delete a function."""
    repo = _init_repo(tmp_path)

    (tmp_path / 'util.py').write_text(textwrap.dedent('''\
        def helper():
            return 1

        def old_func():
            return 2
    '''))
    _commit(repo, 'Initial')

    (tmp_path / 'util.py').write_text(textwrap.dedent('''\
        def helper():
            return 1
    '''))
    _commit(repo, 'Remove old_func')

    return tmp_path


@pytest.fixture
def added_file_repo(tmp_path):
    """Two-commit repo: initial → add a new file."""
    repo = _init_repo(tmp_path)

    (tmp_path / 'existing.py').write_text('def existing(): pass\n')
    _commit(repo, 'Initial')

    (tmp_path / 'new_module.py').write_text(textwrap.dedent('''\
        def brand_new():
            return 42
    '''))
    _commit(repo, 'Add new_module')

    return tmp_path


@pytest.fixture
def deleted_file_repo(tmp_path):
    """Two-commit repo: initial → delete a file."""
    repo = _init_repo(tmp_path)

    (tmp_path / 'keep.py').write_text('def keep(): pass\n')
    (tmp_path / 'remove_me.py').write_text('def doomed(): pass\n')
    _commit(repo, 'Initial')

    (tmp_path / 'remove_me.py').unlink()
    repo.index.remove(['remove_me.py'])
    repo.index.commit('Delete remove_me')

    return tmp_path


@pytest.fixture
def multi_module_repo(tmp_path):
    """Repo with cross-module dependencies for impact testing."""
    repo = _init_repo(tmp_path)

    (tmp_path / 'models.py').write_text(textwrap.dedent('''\
        class User:
            def __init__(self, name):
                self.name = name
    '''))

    (tmp_path / 'service.py').write_text(textwrap.dedent('''\
        from models import User

        def create_user(name):
            return User(name)

        def get_user(uid):
            return None
    '''))

    (tmp_path / 'api.py').write_text(textwrap.dedent('''\
        from service import create_user, get_user

        def handle_create(req):
            return create_user(req["name"])

        def handle_get(req):
            return get_user(req["id"])
    '''))
    _commit(repo, 'Initial application')

    # Commit 2: modify create_user (has dependents in api.py)
    (tmp_path / 'service.py').write_text(textwrap.dedent('''\
        from models import User

        def create_user(name, email=None):
            """Now accepts email."""
            u = User(name)
            u.email = email
            return u

        def get_user(uid):
            return None
    '''))
    _commit(repo, 'Add email param to create_user')

    return tmp_path


@pytest.fixture
def class_change_repo(tmp_path):
    """Repo where a class method is modified."""
    repo = _init_repo(tmp_path)

    (tmp_path / 'engine.py').write_text(textwrap.dedent('''\
        class Engine:
            def run(self):
                return "running"

            def stop(self):
                return "stopped"
    '''))
    _commit(repo, 'Initial')

    (tmp_path / 'engine.py').write_text(textwrap.dedent('''\
        class Engine:
            def run(self, turbo=False):
                if turbo:
                    return "turbo"
                return "running"

            def stop(self):
                return "stopped"
    '''))
    _commit(repo, 'Add turbo to Engine.run')

    return tmp_path


# ---------------------------------------------------------------
# Git Service — Validation
# ---------------------------------------------------------------

class TestGitValidation:
    def test_valid_repo(self, git_service, basic_repo):
        assert git_service.validate_repo(basic_repo) is True

    def test_invalid_path(self, git_service, tmp_path):
        assert git_service.validate_repo(tmp_path / 'nope') is False

    def test_non_git_dir(self, git_service, tmp_path):
        (tmp_path / 'plain').mkdir()
        assert git_service.validate_repo(tmp_path / 'plain') is False

    def test_open_valid(self, git_service, basic_repo):
        repo = git_service.open_repo(basic_repo)
        assert repo is not None

    def test_open_nonexistent(self, git_service, tmp_path):
        with pytest.raises(FileNotFoundError):
            git_service.open_repo(tmp_path / 'nope')

    def test_open_non_git(self, git_service, tmp_path):
        (tmp_path / 'plain').mkdir()
        with pytest.raises(ValueError, match='Not a Git repository'):
            git_service.open_repo(tmp_path / 'plain')


# ---------------------------------------------------------------
# Git Service — Commit Retrieval
# ---------------------------------------------------------------

class TestCommitRetrieval:
    def test_commit_info(self, git_service, basic_repo):
        repo = git_service.open_repo(basic_repo)
        head_hash = repo.head.commit.hexsha
        info = git_service.get_commit_info(repo, head_hash)
        assert info.commit_hash == head_hash
        assert info.short_hash == head_hash[:7]
        assert info.author == 'Test'
        assert info.message == 'Modify process, add transform'
        assert info.parent_hash is not None

    def test_invalid_commit(self, git_service, basic_repo):
        repo = git_service.open_repo(basic_repo)
        with pytest.raises(ValueError, match='Invalid commit'):
            git_service.get_commit_info(repo, 'deadbeef' * 5)

    def test_parent_commit(self, git_service, basic_repo):
        repo = git_service.open_repo(basic_repo)
        info = git_service.get_commit_info(repo, repo.head.commit.hexsha)
        parent_info = git_service.get_commit_info(repo, info.parent_hash)
        assert parent_info.message == 'Initial commit'

    def test_initial_commit_has_no_parent(self, git_service, basic_repo):
        repo = git_service.open_repo(basic_repo)
        initial = list(repo.iter_commits())[-1]
        info = git_service.get_commit_info(repo, initial.hexsha)
        assert info.parent_hash is None


# ---------------------------------------------------------------
# Git Service — File Changes
# ---------------------------------------------------------------

class TestFileChanges:
    def test_modified_file(self, git_service, basic_repo):
        repo = git_service.open_repo(basic_repo)
        changes = git_service.get_file_changes(repo, repo.head.commit.hexsha)
        paths = [c.path for c in changes]
        assert 'service.py' in paths
        mod = next(c for c in changes if c.path == 'service.py')
        assert mod.change_type == ChangeType.MODIFIED

    def test_added_file(self, git_service, added_file_repo):
        repo = git_service.open_repo(added_file_repo)
        changes = git_service.get_file_changes(repo, repo.head.commit.hexsha)
        added = [c for c in changes if c.change_type == ChangeType.ADDED]
        assert any(c.path == 'new_module.py' for c in added)

    def test_deleted_file(self, git_service, deleted_file_repo):
        repo = git_service.open_repo(deleted_file_repo)
        changes = git_service.get_file_changes(repo, repo.head.commit.hexsha)
        deleted = [c for c in changes if c.change_type == ChangeType.DELETED]
        assert any(c.path == 'remove_me.py' for c in deleted)

    def test_initial_commit_all_added(self, git_service, basic_repo):
        repo = git_service.open_repo(basic_repo)
        initial = list(repo.iter_commits())[-1]
        changes = git_service.get_file_changes(repo, initial.hexsha)
        assert all(c.change_type == ChangeType.ADDED for c in changes)

    def test_line_counts(self, git_service, basic_repo):
        repo = git_service.open_repo(basic_repo)
        changes = git_service.get_file_changes(repo, repo.head.commit.hexsha)
        mod = next(c for c in changes if c.path == 'service.py')
        assert mod.additions > 0

    def test_file_at_commit(self, git_service, basic_repo):
        repo = git_service.open_repo(basic_repo)
        content = git_service.get_file_at_commit(
            repo, repo.head.commit.hexsha, 'service.py',
        )
        assert 'transform' in content

    def test_file_at_parent(self, git_service, basic_repo):
        repo = git_service.open_repo(basic_repo)
        parent = repo.head.commit.parents[0].hexsha
        content = git_service.get_file_at_commit(repo, parent, 'service.py')
        assert 'transform' not in content


# ---------------------------------------------------------------
# Change Detector — Function-level
# ---------------------------------------------------------------

class TestChangeDetector:
    def test_modified_function(self, change_detector, basic_repo):
        repo = git.Repo(str(basic_repo))
        gs = GitService()
        file_changes = gs.get_file_changes(repo, repo.head.commit.hexsha)
        components = change_detector.detect_changes(
            repo, repo.head.commit.hexsha, file_changes,
        )
        modified = [
            c for c in components
            if c.change_type == ComponentChangeType.MODIFIED
        ]
        assert any(c.name == 'process' for c in modified)

    def test_added_function(self, change_detector, basic_repo):
        repo = git.Repo(str(basic_repo))
        gs = GitService()
        file_changes = gs.get_file_changes(repo, repo.head.commit.hexsha)
        components = change_detector.detect_changes(
            repo, repo.head.commit.hexsha, file_changes,
        )
        added = [
            c for c in components
            if c.change_type == ComponentChangeType.ADDED
        ]
        assert any(c.name == 'transform' for c in added)

    def test_removed_function(self, change_detector, delete_repo):
        repo = git.Repo(str(delete_repo))
        gs = GitService()
        file_changes = gs.get_file_changes(repo, repo.head.commit.hexsha)
        components = change_detector.detect_changes(
            repo, repo.head.commit.hexsha, file_changes,
        )
        removed = [
            c for c in components
            if c.change_type == ComponentChangeType.REMOVED
        ]
        assert any(c.name == 'old_func' for c in removed)

    def test_unchanged_not_reported(self, change_detector, basic_repo):
        repo = git.Repo(str(basic_repo))
        gs = GitService()
        file_changes = gs.get_file_changes(repo, repo.head.commit.hexsha)
        components = change_detector.detect_changes(
            repo, repo.head.commit.hexsha, file_changes,
        )
        names = [c.name for c in components]
        assert 'validate' not in names

    def test_added_file_all_added(self, change_detector, added_file_repo):
        repo = git.Repo(str(added_file_repo))
        gs = GitService()
        file_changes = gs.get_file_changes(repo, repo.head.commit.hexsha)
        components = change_detector.detect_changes(
            repo, repo.head.commit.hexsha, file_changes,
        )
        assert all(c.change_type == ComponentChangeType.ADDED for c in components)
        assert any(c.name == 'brand_new' for c in components)

    def test_deleted_file_all_removed(self, change_detector, deleted_file_repo):
        repo = git.Repo(str(deleted_file_repo))
        gs = GitService()
        file_changes = gs.get_file_changes(repo, repo.head.commit.hexsha)
        components = change_detector.detect_changes(
            repo, repo.head.commit.hexsha, file_changes,
        )
        removed = [
            c for c in components
            if c.change_type == ComponentChangeType.REMOVED
        ]
        assert any(c.name == 'doomed' for c in removed)

    def test_class_method_modified(self, change_detector, class_change_repo):
        repo = git.Repo(str(class_change_repo))
        gs = GitService()
        file_changes = gs.get_file_changes(repo, repo.head.commit.hexsha)
        components = change_detector.detect_changes(
            repo, repo.head.commit.hexsha, file_changes,
        )
        modified = [
            c for c in components
            if c.change_type == ComponentChangeType.MODIFIED
        ]
        assert any(c.name == 'run' for c in modified)
        run_change = next(c for c in modified if c.name == 'run')
        assert run_change.component_id == 'method:engine.Engine.run'

    def test_class_method_unchanged(self, change_detector, class_change_repo):
        repo = git.Repo(str(class_change_repo))
        gs = GitService()
        file_changes = gs.get_file_changes(repo, repo.head.commit.hexsha)
        components = change_detector.detect_changes(
            repo, repo.head.commit.hexsha, file_changes,
        )
        names = [c.name for c in components]
        assert 'stop' not in names

    def test_component_id_format(self, change_detector, basic_repo):
        repo = git.Repo(str(basic_repo))
        gs = GitService()
        file_changes = gs.get_file_changes(repo, repo.head.commit.hexsha)
        components = change_detector.detect_changes(
            repo, repo.head.commit.hexsha, file_changes,
        )
        mod_process = next(c for c in components if c.name == 'process')
        assert mod_process.component_id == 'function:service.process'

    def test_initial_commit(self, change_detector, basic_repo):
        repo = git.Repo(str(basic_repo))
        gs = GitService()
        initial = list(repo.iter_commits())[-1]
        file_changes = gs.get_file_changes(repo, initial.hexsha)
        components = change_detector.detect_changes(
            repo, initial.hexsha, file_changes,
        )
        assert all(c.change_type == ComponentChangeType.ADDED for c in components)


# ---------------------------------------------------------------
# Impact Analyzer
# ---------------------------------------------------------------

class TestImpactAnalyzer:
    def test_direct_impact(self, multi_module_repo):
        analyzer = ImpactAnalyzer()
        result = analyzer.analyze_commit(
            multi_module_repo, 'HEAD',
        )
        # create_user was modified; api.py calls create_user
        direct_ids = [i.component_id for i in result.direct_impact]
        assert any('api' in cid for cid in direct_ids)

    def test_changed_components(self, multi_module_repo):
        analyzer = ImpactAnalyzer()
        result = analyzer.analyze_commit(
            multi_module_repo, 'HEAD',
        )
        changed_names = [c.name for c in result.changed_components]
        assert 'create_user' in changed_names

    def test_blast_radius(self, multi_module_repo):
        analyzer = ImpactAnalyzer()
        result = analyzer.analyze_commit(
            multi_module_repo, 'HEAD',
        )
        br = result.blast_radius
        assert br.changed_file_count >= 1
        assert br.changed_component_count >= 1
        assert br.total_affected_count >= br.changed_component_count

    def test_file_changes_present(self, multi_module_repo):
        analyzer = ImpactAnalyzer()
        result = analyzer.analyze_commit(
            multi_module_repo, 'HEAD',
        )
        assert any(fc.path == 'service.py' for fc in result.file_changes)

    def test_commit_info(self, multi_module_repo):
        analyzer = ImpactAnalyzer()
        result = analyzer.analyze_commit(
            multi_module_repo, 'HEAD',
        )
        assert result.commit.message == 'Add email param to create_user'

    def test_invalid_commit(self, multi_module_repo):
        analyzer = ImpactAnalyzer()
        with pytest.raises(ValueError):
            analyzer.analyze_commit(
                multi_module_repo, 'deadbeef' * 5,
            )

    def test_non_git_repo(self, tmp_path):
        (tmp_path / 'plain').mkdir()
        analyzer = ImpactAnalyzer()
        with pytest.raises(ValueError):
            analyzer.analyze_commit(tmp_path / 'plain', 'HEAD')


# ---------------------------------------------------------------
# API Endpoint
# ---------------------------------------------------------------

class TestCommitEndpoint:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_commit_endpoint_success(self, client, multi_module_repo):
        response = client.post('/api/analyze/commit', json={
            'path': str(multi_module_repo),
            'commit': 'HEAD',
        })
        assert response.status_code == 200
        data = response.json()
        assert 'commit' in data
        assert 'file_changes' in data
        assert 'changed_components' in data
        assert 'direct_impact' in data
        assert 'transitive_impact' in data
        assert 'blast_radius' in data

    def test_commit_endpoint_invalid_path(self, client):
        response = client.post('/api/analyze/commit', json={
            'path': '/nonexistent/repo',
            'commit': 'HEAD',
        })
        assert response.status_code in (400, 404)

    def test_commit_endpoint_invalid_commit(self, client, multi_module_repo):
        response = client.post('/api/analyze/commit', json={
            'path': str(multi_module_repo),
            'commit': 'deadbeef' * 5,
        })
        assert response.status_code == 400

    def test_commit_endpoint_non_git(self, client, tmp_path):
        (tmp_path / 'plain').mkdir()
        response = client.post('/api/analyze/commit', json={
            'path': str(tmp_path / 'plain'),
            'commit': 'HEAD',
        })
        assert response.status_code == 400
