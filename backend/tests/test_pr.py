"""Tests for Pull Request Analysis."""

import json
import os
import subprocess
import textwrap
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.analyzers.pr_analyzer import PRAnalyzer
from app.models.pr_models import PRAnalysisResult
from app.main import app

@pytest.fixture
def pr_repo(tmp_path: Path) -> Path:
    """A Git repository for testing PR analysis."""
    repo_dir = tmp_path / 'pr_repo'
    repo_dir.mkdir()
    
    # Init git
    subprocess.run(['git', 'init'], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test'], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=repo_dir, check=True, capture_output=True)
    
    # Base commit
    (repo_dir / 'utils.py').write_text(textwrap.dedent('''
        def old_func():
            return 1
            
        def untouched_func():
            return 2
    ''').lstrip())
    
    (repo_dir / 'logic.py').write_text(textwrap.dedent('''
        from utils import old_func
        
        def process():
            return old_func()
    ''').lstrip())
    
    subprocess.run(['git', 'add', '.'], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=repo_dir, check=True, capture_output=True)
    
    # Tag base commit
    subprocess.run(['git', 'tag', 'base'], cwd=repo_dir, check=True, capture_output=True)
    
    # Head commit
    # Modify utils.py
    (repo_dir / 'utils.py').write_text(textwrap.dedent('''
        def old_func(x):
            if x > 0:
                return x
            return 1
            
        def untouched_func():
            return 2
            
        def new_func():
            return 3
    ''').lstrip())
    
    # Modify logic.py
    (repo_dir / 'logic.py').write_text(textwrap.dedent('''
        from utils import old_func, new_func
        
        def process():
            return old_func(1) + new_func()
    ''').lstrip())
    
    # Add a new file
    (repo_dir / 'api.py').write_text(textwrap.dedent('''
        from fastapi import FastAPI
        from logic import process
        
        app = FastAPI()
        
        @app.get("/data")
        def get_data():
            return process()
    ''').lstrip())
    
    # Delete a file (we'll just create and delete one in the same branch)
    (repo_dir / 'deleted.py').write_text('def deleted_func(): return 4\n')
    subprocess.run(['git', 'add', '.'], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'Add deleted file'], cwd=repo_dir, check=True, capture_output=True)
    
    subprocess.run(['git', 'rm', 'deleted.py'], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'Remove deleted file'], cwd=repo_dir, check=True, capture_output=True)
    
    # Tag head commit
    subprocess.run(['git', 'tag', 'head_tag'], cwd=repo_dir, check=True, capture_output=True)
    
    return repo_dir


def test_pr_analyzer(pr_repo: Path):
    """Test full PR Analyzer pipeline."""
    analyzer = PRAnalyzer()
    
    # resolve hashes
    base_hash = subprocess.run(['git', 'rev-parse', 'base'], cwd=pr_repo, capture_output=True, text=True).stdout.strip()
    head_hash = subprocess.run(['git', 'rev-parse', 'head_tag'], cwd=pr_repo, capture_output=True, text=True).stdout.strip()
    
    result = analyzer.analyze_pr(pr_repo, base_hash, head_hash)
    
    assert result.base_commit.commit_hash == base_hash
    assert result.head_commit.commit_hash == head_hash
    
    # Check file changes
    paths = [fc.path for fc in result.file_changes]
    assert 'utils.py' in paths
    assert 'logic.py' in paths
    assert 'api.py' in paths
    
    # Check component changes
    c_ids = [cc.component_id for cc in result.changed_components]
    assert 'function:utils.old_func' in c_ids  # modified
    assert 'function:utils.new_func' in c_ids  # added
    assert 'function:logic.process' in c_ids   # modified
    assert 'function:api.get_data' in c_ids    # added
    
    # Complexity delta
    assert result.complexity_delta.functions_added > 0
    
    # Risk
    assert result.risk.score >= 0


def test_pr_analyzer_invalid_commits(pr_repo: Path):
    """Test PR analysis with invalid commits."""
    analyzer = PRAnalyzer()
    with pytest.raises(ValueError):
        analyzer.analyze_pr(pr_repo, 'invalid_base', 'invalid_head')


def test_pr_api_endpoint(client: TestClient, pr_repo: Path):
    """Test /api/analyze/pr endpoint."""
    base_hash = subprocess.run(['git', 'rev-parse', 'base'], cwd=pr_repo, capture_output=True, text=True).stdout.strip()
    head_hash = subprocess.run(['git', 'rev-parse', 'head_tag'], cwd=pr_repo, capture_output=True, text=True).stdout.strip()
    
    payload = {
        'path': str(pr_repo),
        'base_commit': base_hash,
        'head_commit': head_hash
    }
    response = client.post('/api/analyze/pr', json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data['base_commit']['commit_hash'] == base_hash
    assert data['head_commit']['commit_hash'] == head_hash
    assert len(data['file_changes']) > 0


def test_pr_cli_execution(pr_repo: Path):
    """Test scopeguard pr CLI command."""
    import sys
    base_hash = subprocess.run(['git', 'rev-parse', 'base'], cwd=pr_repo, capture_output=True, text=True).stdout.strip()
    head_hash = subprocess.run(['git', 'rev-parse', 'head_tag'], cwd=pr_repo, capture_output=True, text=True).stdout.strip()
    
    cmd = [
        sys.executable, '-m', 'app.cli.main', 
        'pr', str(pr_repo), 
        '--base', base_hash,
        '--head', head_hash,
        '--json'
    ]
    
    backend_dir = Path(__file__).parent.parent
    result = subprocess.run(cmd, cwd=str(backend_dir), capture_output=True, text=True)
    
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data['base_commit']['commit_hash'] == base_hash
    assert data['head_commit']['commit_hash'] == head_hash


def test_pr_analyzer_same_commit(pr_repo: Path):
    """Test 8: Same base/head commit."""
    analyzer = PRAnalyzer()
    base_hash = subprocess.run(['git', 'rev-parse', 'base'], cwd=pr_repo, capture_output=True, text=True).stdout.strip()
    
    result = analyzer.analyze_pr(pr_repo, base_hash, base_hash)
    
    assert len(result.file_changes) == 0
    assert len(result.changed_components) == 0
    assert result.total_additions == 0
    assert result.total_deletions == 0
    assert result.blast_radius.total_affected_count == 0


def test_pr_analyzer_test_only_change(pr_repo: Path):
    """Test 10: Test-only change."""
    # Create a branch from base and add a test
    subprocess.run(['git', 'checkout', '-b', 'test-branch', 'base'], cwd=pr_repo, check=True, capture_output=True)
    
    (pr_repo / 'test_logic.py').write_text(textwrap.dedent('''
        from logic import process
        def test_process():
            assert process() == 1
    ''').lstrip())
    
    subprocess.run(['git', 'add', 'test_logic.py'], cwd=pr_repo, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'Add test'], cwd=pr_repo, check=True, capture_output=True)
    
    test_head_hash = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=pr_repo, capture_output=True, text=True).stdout.strip()
    base_hash = subprocess.run(['git', 'rev-parse', 'base'], cwd=pr_repo, capture_output=True, text=True).stdout.strip()
    
    analyzer = PRAnalyzer()
    result = analyzer.analyze_pr(pr_repo, base_hash, test_head_hash)
    
    # We added a file, it's a test file
    assert len(result.file_changes) == 1
    assert result.file_changes[0].path == 'test_logic.py'
    
    # Switch back to main to avoid breaking other tests
    subprocess.run(['git', 'checkout', 'master'], cwd=pr_repo, check=False, capture_output=True)


def test_pr_analyzer_risk_test_impact_recommendations(pr_repo: Path):
    """Test 13, 14, 15: Risk, test impact, and recommendations."""
    analyzer = PRAnalyzer()
    base_hash = subprocess.run(['git', 'rev-parse', 'base'], cwd=pr_repo, capture_output=True, text=True).stdout.strip()
    head_hash = subprocess.run(['git', 'rev-parse', 'head_tag'], cwd=pr_repo, capture_output=True, text=True).stdout.strip()
    
    result = analyzer.analyze_pr(pr_repo, base_hash, head_hash)
    
    # Risk
    assert result.risk.score > 0
    assert len(result.risk.factors) > 0
    
    # Test impact
    # Since there are no tests in this specific test repo setup by default, total_tests will be 0.
    # We can at least check that the struct is populated.
    assert result.test_selection is not None
    assert hasattr(result.test_selection, 'total_tests')
    assert hasattr(result.test_selection, 'selected_tests')
    
    # Recommendations
    assert len(result.risk.recommendations) > 0
    
    # Hotspot touched (Test 12)
    # The dummy repo is too small to trigger hotspots naturally, but we verify the field exists.
    assert hasattr(result, 'hotspots_touched')
    assert isinstance(result.hotspot_count, int)


def test_pr_analyzer_readonly_behavior(pr_repo: Path):
    """Test 19, 20: Repository and Git history remain unchanged."""
    import os
    
    # Record state before
    base_hash = subprocess.run(['git', 'rev-parse', 'base'], cwd=pr_repo, capture_output=True, text=True).stdout.strip()
    head_hash = subprocess.run(['git', 'rev-parse', 'head_tag'], cwd=pr_repo, capture_output=True, text=True).stdout.strip()
    
    before_files = set(os.listdir(pr_repo))
    before_mtimes = {f: os.path.getmtime(pr_repo / f) for f in before_files if (pr_repo / f).is_file()}
    before_log = subprocess.run(['git', 'log', '--oneline'], cwd=pr_repo, capture_output=True, text=True).stdout
    before_status = subprocess.run(['git', 'status', '--porcelain'], cwd=pr_repo, capture_output=True, text=True).stdout
    
    analyzer = PRAnalyzer()
    analyzer.analyze_pr(pr_repo, base_hash, head_hash)
    
    # Check state after
    after_files = set(os.listdir(pr_repo))
    after_mtimes = {f: os.path.getmtime(pr_repo / f) for f in after_files if (pr_repo / f).is_file()}
    after_log = subprocess.run(['git', 'log', '--oneline'], cwd=pr_repo, capture_output=True, text=True).stdout
    after_status = subprocess.run(['git', 'status', '--porcelain'], cwd=pr_repo, capture_output=True, text=True).stdout
    
    assert before_files == after_files
    assert before_mtimes == after_mtimes
    assert before_log == after_log
    assert before_status == after_status
