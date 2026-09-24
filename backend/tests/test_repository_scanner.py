"""Tests for the repository scanner."""

from pathlib import Path

import pytest

from app.analyzers.repository_scanner import RepositoryScanner


@pytest.fixture
def scanner():
    return RepositoryScanner()


class TestFileDiscovery:
    """Tests for Python file discovery."""

    def test_discovers_python_files(self, scanner: RepositoryScanner, tmp_repo: Path):
        files = scanner.discover_python_files(tmp_repo)
        filenames = [f.name for f in files]

        assert 'simple.py' in filenames
        assert 'classes.py' in filenames
        assert 'routes.py' in filenames
        assert 'caller.py' in filenames
        assert 'broken.py' in filenames

    def test_discovers_files_in_subdirectories(self, scanner: RepositoryScanner, tmp_repo: Path):
        files = scanner.discover_python_files(tmp_repo)
        filenames = [f.name for f in files]
        assert 'helper.py' in filenames

    def test_excludes_venv_directory(self, scanner: RepositoryScanner, tmp_repo: Path):
        files = scanner.discover_python_files(tmp_repo)
        # Check that no file comes from within the venv directory
        relative_paths = [str(f.relative_to(tmp_repo)) for f in files]
        assert not any(
            'venv' in Path(p).parts for p in relative_paths
        )

    def test_excludes_pycache_directory(self, scanner: RepositoryScanner, tmp_repo: Path):
        files = scanner.discover_python_files(tmp_repo)
        relative_paths = [str(f.relative_to(tmp_repo)) for f in files]
        assert not any(
            '__pycache__' in Path(p).parts for p in relative_paths
        )

    def test_empty_directory(self, scanner: RepositoryScanner, tmp_path: Path):
        files = scanner.discover_python_files(tmp_path)
        assert files == []


class TestRepositoryScanning:
    """Tests for full repository scanning."""

    def test_scan_produces_results(self, scanner: RepositoryScanner, tmp_repo: Path):
        result = scanner.scan(tmp_repo)

        assert result.repository_path == str(tmp_repo)
        assert len(result.files) > 0
        assert result.summary.total_files > 0

    def test_scan_summary_counts(self, scanner: RepositoryScanner, tmp_repo: Path):
        result = scanner.scan(tmp_repo)

        assert result.summary.total_functions > 0
        assert result.summary.total_classes > 0
        assert result.summary.total_imports > 0

    def test_scan_detects_routes(self, scanner: RepositoryScanner, tmp_repo: Path):
        result = scanner.scan(tmp_repo)
        assert result.summary.total_routes > 0

    def test_scan_handles_syntax_errors(self, scanner: RepositoryScanner, tmp_repo: Path):
        result = scanner.scan(tmp_repo)
        assert result.summary.files_with_errors > 0
        assert len(result.warnings) > 0

    def test_scan_nonexistent_path(self, scanner: RepositoryScanner):
        with pytest.raises(FileNotFoundError):
            scanner.scan('/nonexistent/path/nowhere')

    def test_scan_file_not_directory(self, scanner: RepositoryScanner, tmp_path: Path):
        f = tmp_path / 'file.py'
        f.write_text('x = 1')
        with pytest.raises(NotADirectoryError):
            scanner.scan(f)

    def test_scan_reports_excluded_dirs(self, scanner: RepositoryScanner, tmp_repo: Path):
        result = scanner.scan(tmp_repo)
        assert len(result.excluded_directories) > 0


class TestAnalysisEndpoint:
    """Tests for the /api/analyze/repository endpoint."""

    def test_analyze_endpoint_success(self, client, tmp_repo: Path):
        response = client.post(
            '/api/analyze/repository',
            json={'path': str(tmp_repo)},
        )
        assert response.status_code == 200
        data = response.json()
        assert 'files' in data
        assert 'summary' in data
        assert data['summary']['total_files'] > 0

    def test_analyze_endpoint_not_found(self, client):
        response = client.post(
            '/api/analyze/repository',
            json={'path': '/nonexistent/repo/path'},
        )
        assert response.status_code == 404

    def test_analyze_endpoint_not_a_directory(self, client, tmp_path: Path):
        f = tmp_path / 'file.txt'
        f.write_text('hello')
        response = client.post(
            '/api/analyze/repository',
            json={'path': str(f)},
        )
        assert response.status_code == 400

    def test_health_endpoint(self, client):
        response = client.get('/health')
        assert response.status_code == 200
        assert response.json()['status'] == 'healthy'

    def test_root_endpoint(self, client):
        response = client.get('/')
        assert response.status_code == 200
        data = response.json()
        assert data['name'] == 'ScopeGuard'
        assert 'version' in data
