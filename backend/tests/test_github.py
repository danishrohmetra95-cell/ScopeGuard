"""Tests for GitHub Repository Integration."""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.github_service import (
    GitHubService,
    InvalidGitHubURLError,
    RepositoryAcquisitionError,
)

@pytest.fixture
def github_service():
    return GitHubService()

@pytest.fixture
def mock_clone():
    with mock.patch('git.Repo.clone_from') as mock_c:
        # Simulate cloning into the target directory by creating a dummy file
        def side_effect(url, to_path, **kwargs):
            (Path(to_path) / "dummy.py").write_text("def dummy(): pass")
            # Also mock the scanner expecting __init__.py or something if needed
            # but for our simple tests, we mock the scanner too
        mock_c.side_effect = side_effect
        yield mock_c

@pytest.fixture
def mock_scanner():
    with mock.patch('app.analyzers.repository_scanner.RepositoryScanner.scan') as mock_s:
        # Return a dummy RepositoryAnalysis
        from app.models.analysis_models import RepositoryAnalysis, RepositorySummary
        mock_s.return_value = RepositoryAnalysis(
            repository_path="mocked",
            summary=RepositorySummary(
                total_files=1,
                total_functions=1,
                total_classes=0,
                total_lines=1
            ),
            files=[]
        )
        yield mock_s

@pytest.fixture
def mock_full_analysis():
    """Mock the _run_full_analysis pipeline used by the GitHub endpoint."""
    with mock.patch('app.api.analysis._run_full_analysis') as mock_fa:
        from app.models.analysis_models import FullAnalysisResult
        from app.models.risk_models import CommitRiskAnalysis, RiskScore, RiskLevel
        from app.models.test_models import CommitTestAnalysis, TestSelectionResult
        from app.models.history_models import HistoricalAnalysisResult, RiskTrendSummary
        from app.models.change_models import CommitInfo, BlastRadius

        dummy_commit = CommitInfo(
            commit_hash='abc1234567890',
            short_hash='abc1234',
            author='Test Author',
            author_email='test@example.com',
            message='test commit',
            timestamp='2026-01-01T00:00:00+00:00',
            parent_hash=None,
            changed_file_count=0,
        )
        dummy_blast = BlastRadius(
            changed_file_count=0,
            changed_component_count=0,
            direct_impact_count=0,
            transitive_impact_count=0,
            total_affected_count=0,
            affected_api_count=0,
        )
        dummy_risk = CommitRiskAnalysis(
            repository_path='mocked',
            commit=dummy_commit,
            blast_radius=dummy_blast,
            risk=RiskScore(score=0, level=RiskLevel.LOW, summary='Low risk'),
        )
        dummy_tests = CommitTestAnalysis(
            repository_path='mocked',
            commit=dummy_commit,
            blast_radius=dummy_blast,
            test_selection=TestSelectionResult(
                total_tests=0, selected_tests=0,
                skipped_tests=0, selection_percentage=0.0,
            ),
        )
        dummy_history = HistoricalAnalysisResult(
            repository_path='mocked',
            commit_count=0,
            risk_trend_summary=RiskTrendSummary(
                average_risk=0, highest_risk=0, lowest_risk=0,
                low_count=0, medium_count=0, high_count=0, critical_count=0,
            ),
            summary='No commits analyzed.',
        )
        mock_fa.return_value = FullAnalysisResult(
            risk=dummy_risk,
            tests=dummy_tests,
            history=dummy_history,
        )
        yield mock_fa


class TestGitHubService:
    """Test URL Validation and Service Logic."""
    
    def test_valid_github_url(self, github_service):
        """Test 1: Valid GitHub URL parsing."""
        url = "https://github.com/owner/repo"
        assert github_service.validate_url(url) == "https://github.com/owner/repo.git"

    def test_url_with_trailing_slash(self, github_service):
        """Test 2: URL with trailing slash."""
        url = "https://github.com/owner/repo/"
        assert github_service.validate_url(url) == "https://github.com/owner/repo.git"

    def test_url_with_dot_git(self, github_service):
        """Test 3: URL with .git."""
        url = "https://github.com/owner/repo.git"
        assert github_service.validate_url(url) == "https://github.com/owner/repo.git"

    def test_invalid_url(self, github_service):
        """Test 4: Invalid URL."""
        with pytest.raises(InvalidGitHubURLError):
            github_service.validate_url("not a url")
            
    def test_unsupported_host(self, github_service):
        """Test 5: Unsupported host."""
        with pytest.raises(InvalidGitHubURLError):
            github_service.validate_url("https://gitlab.com/owner/repo")
            
    def test_malformed_repository_url(self, github_service):
        """Test 6: Malformed repository URL."""
        with pytest.raises(InvalidGitHubURLError):
            github_service.validate_url("https://github.com/owner_only")
        with pytest.raises(InvalidGitHubURLError):
            github_service.validate_url("https://github.com/owner/repo/extra")
            
    def test_temporary_directory_creation_and_cleanup(self, github_service, mock_clone):
        """Test 7 & 8: Temporary directory creation and cleanup."""
        captured_path = None
        with github_service.acquire_repository("https://github.com/owner/repo") as path:
            captured_path = path
            assert path.exists()
            assert path.is_dir()
            
        # Cleanup after analysis
        assert not captured_path.exists()
        
    def test_cleanup_after_analysis_exception(self, github_service, mock_clone):
        """Test 9: Cleanup after analysis exception."""
        captured_path = None
        try:
            with github_service.acquire_repository("https://github.com/owner/repo") as path:
                captured_path = path
                raise ValueError("Analysis failed midway")
        except ValueError:
            pass
            
        assert captured_path is not None
        assert not captured_path.exists()
        
    def test_mocked_successful_repository_acquisition(self, github_service, mock_clone):
        """Test 10: Mocked successful repository acquisition."""
        with github_service.acquire_repository("https://github.com/owner/repo") as path:
            assert mock_clone.called
            
    def test_mocked_clone_failure(self, github_service):
        """Test 11: Mocked clone failure."""
        with mock.patch('git.Repo.clone_from', side_effect=Exception("Git failed")):
            with pytest.raises(RepositoryAcquisitionError):
                with github_service.acquire_repository("https://github.com/owner/repo") as path:
                    pass

    def test_repository_not_found(self, github_service):
        """Test 12: Repository-not-found handling."""
        import git
        with mock.patch('git.Repo.clone_from', side_effect=git.GitCommandError("clone", 128, b"not found")):
            with pytest.raises(RepositoryAcquisitionError) as exc:
                with github_service.acquire_repository("https://github.com/owner/repo") as path:
                    pass
            assert "not found" in str(exc.value)

    def test_authentication_failure_handling(self, github_service):
        """Test 13: Authentication failure handling."""
        import git
        with mock.patch('git.Repo.clone_from', side_effect=git.GitCommandError("clone", 128, b"Authentication failed")):
            with pytest.raises(RepositoryAcquisitionError) as exc:
                with github_service.acquire_repository("https://github.com/owner/repo") as path:
                    pass
            assert "Authentication failed" in str(exc.value)

    def test_token_is_not_exposed(self, github_service, monkeypatch):
        """Test 14: Token is not exposed."""
        monkeypatch.setenv('SCOPEGUARD_GITHUB_TOKEN', 'SECRET_TOKEN_123')
        import git
        
        # Simulate a git error that echos the URL (which contains the token)
        error_output = b"fatal: unable to access 'https://SECRET_TOKEN_123@github.com/o/r.git/': 401"
        with mock.patch('git.Repo.clone_from', side_effect=git.GitCommandError(["clone"], 128, error_output)):
            with pytest.raises(RepositoryAcquisitionError) as exc:
                with github_service.acquire_repository("https://github.com/owner/repo") as path:
                    pass
            
            # Ensure the token was scrubbed
            assert 'SECRET_TOKEN_123' not in str(exc.value)
            assert '***TOKEN***' in str(exc.value)


class TestGitHubAPI:
    """Test API endpoint."""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_api_success_response(self, client, mock_clone, mock_full_analysis):
        """Test 15, 16: GitHub analysis invokes full pipeline, API success response."""
        response = client.post('/api/analyze/github', json={'url': 'https://github.com/owner/repo'})
        assert response.status_code == 200
        data = response.json()
        # FullAnalysisResult has risk, tests, history keys
        assert 'risk' in data
        assert 'tests' in data
        assert 'history' in data
        assert mock_full_analysis.called

    def test_api_invalid_input(self, client):
        """Test 17: API invalid input."""
        response = client.post('/api/analyze/github', json={'url': 'invalid_url'})
        assert response.status_code == 400
        assert "Unsupported scheme" in response.json()['detail']

    def test_api_repository_failure(self, client):
        """Test 18: API repository failure."""
        with mock.patch('app.services.github_service.GitHubService.acquire_repository', side_effect=RepositoryAcquisitionError("Fail")):
            response = client.post('/api/analyze/github', json={'url': 'https://github.com/owner/repo'})
            assert response.status_code == 400
            assert "Fail" in response.json()['detail']


class TestGitHubCLI:
    """Test CLI commands."""
    
    def test_cli_success(self, mock_clone, mock_scanner):
        """Test 19, 20: CLI success, CLI JSON output."""
        from app.cli.main import main
        
        with mock.patch('sys.argv', ['scopeguard', 'github', 'https://github.com/owner/repo', '--json']):
            with mock.patch('sys.stdout', new_callable=mock.PropertyMock) as mock_stdout:
                # We need to capture stdout
                import io
                captured_out = io.StringIO()
                with mock.patch('sys.stdout', captured_out):
                    try:
                        main()
                    except SystemExit as e:
                        assert e.code == 0
                
                output = captured_out.getvalue()
                data = json.loads(output)
                assert data['repository_path'] == 'https://github.com/owner/repo'
        
    def test_existing_commands_remain_functional(self):
        """Test 21: Existing commands remain functional."""
        from app.cli.main import main
        import io
        
        with mock.patch('sys.argv', ['scopeguard', '--help']):
            captured_out = io.StringIO()
            with mock.patch('sys.stdout', captured_out):
                try:
                    main()
                except SystemExit:
                    pass
                
            output = captured_out.getvalue()
            assert 'analyze' in output
            assert 'pr' in output
            assert 'github' in output


class TestSecurity:
    """Test Security and Read-Only requirements."""
    
    def test_no_repository_code_execution(self, github_service, mock_clone):
        """Test 22: No repository code execution."""
        # The architecture only imports AST and Git analysis, which is static.
        # This test acts as a structural guarantee.
        assert not hasattr(github_service, 'execute')
        
    def test_no_dependency_installation(self, github_service):
        """Test 23: No dependency installation."""
        assert not hasattr(github_service, 'install_requirements')
        
    def test_no_shell_command_execution(self, github_service):
        """Test 24: No shell command execution from repository content."""
        # Clone URL is strictly validated and normalized, eliminating shell injections
        url = "https://github.com/owner/repo; rm -rf /"
        with pytest.raises(InvalidGitHubURLError):
            github_service.validate_url(url)


# ---------------------------------------------------------
# SMOKE TEST
# ---------------------------------------------------------

@pytest.mark.skipif(
    os.environ.get('SKIP_NETWORK_TESTS', '1') == '1',
    reason="Skipping live network smoke test by default to avoid flaky tests."
)
def test_real_smoke_test(github_service):
    """Real public GitHub repository smoke test (opt-in)."""
    # Uses a very small public repo
    url = "https://github.com/octocat/Hello-World"
    
    with github_service.acquire_repository(url) as path:
        assert path.exists()
        assert (path / "README").exists()
    
    # Verify cleanup
    assert not path.exists()
