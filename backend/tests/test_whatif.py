"""Tests for the What-If impact simulator."""

import json
import subprocess
import textwrap
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.analyzers.whatif_analyzer import WhatIfAnalyzer
from app.models.whatif_models import WhatIfResult
from app.main import app

@pytest.fixture
def whatif_repo(tmp_path: Path) -> Path:
    """A repository for what-if simulations with APIs, tests, and dependencies."""
    
    # Base utility (no dependents yet, wait yes, logic depends on it)
    (tmp_path / 'utils.py').write_text(textwrap.dedent('''
        def format_data(data):
            return str(data)
            
        class Formatter:
            def format(self, data):
                return str(data)
    ''').lstrip())
    
    # Core logic (depends on utils)
    (tmp_path / 'logic.py').write_text(textwrap.dedent('''
        from utils import format_data
        
        def process(data):
            return format_data(data)
    ''').lstrip())
    
    # API route (depends on logic)
    (tmp_path / 'api.py').write_text(textwrap.dedent('''
        from fastapi import FastAPI
        from logic import process
        
        app = FastAPI()
        
        @app.post("/data")
        def handle_data(data: dict):
            return process(data)
    ''').lstrip())
    
    # Test (depends on logic)
    (tmp_path / 'test_logic.py').write_text(textwrap.dedent('''
        from logic import process
        
        def test_process():
            assert process(1) == "1"
    ''').lstrip())
    
    # Circular dependencies
    (tmp_path / 'circ_a.py').write_text('from circ_b import func_b\ndef func_a():\n    func_b()\n')
    (tmp_path / 'circ_b.py').write_text('from circ_a import func_a\ndef func_b():\n    func_a()\n')
    
    # Unresolved dependency
    (tmp_path / 'broken.py').write_text('from missing_module import unknown_func\ndef broken():\n    unknown_func()\n')
    
    return tmp_path


def test_whatif_existing_function(whatif_repo: Path):
    """Test 2, 7, 8: Existing function with direct and transitive dependents."""
    analyzer = WhatIfAnalyzer()
    
    # utils.format_data is used by logic.process, which is used by api.handle_data and test_logic.test_process
    result = analyzer.simulate(whatif_repo, 'function:utils.format_data')
    
    assert result.component_id == 'function:utils.format_data'
    assert result.component_type == 'function'
    assert result.simulation is True
    
    # direct impact: module:utils (contains it), module:logic (calls it)
    assert 'module:logic' in result.direct_impact
    assert 'module:utils' in result.direct_impact
    
    # transitive impact: module:api, module:test_logic (they call logic.process)
    assert 'module:api' in result.transitive_impact
    assert 'module:test_logic' in result.transitive_impact


def test_whatif_existing_class_and_method(whatif_repo: Path):
    """Test 3, 4, 6: Existing class/method — structural relationships."""
    analyzer = WhatIfAnalyzer()

    result_class = analyzer.simulate(whatif_repo, 'class:utils.Formatter')
    assert result_class.component_type == 'class'
    # module:utils is the direct dependent (CONTAINS edge)
    assert result_class.direct_impact == ['module:utils']
    # Transitive impact flows through module:utils to downstream modules
    assert result_class.blast_radius.direct_impact_count == 1

    result_method = analyzer.simulate(whatif_repo, 'method:utils.Formatter.format')
    assert result_method.component_type == 'method'
    # class:utils.Formatter is the parent (CONTAINS edge)
    assert 'class:utils.Formatter' in result_method.direct_impact


def test_whatif_existing_module(whatif_repo: Path):
    """Test 1: Existing module."""
    analyzer = WhatIfAnalyzer()
    result = analyzer.simulate(whatif_repo, 'module:utils')
    assert result.component_type == 'module'
    assert 'module:logic' in result.direct_impact


def test_whatif_invalid_component(whatif_repo: Path):
    """Test 5: Invalid component."""
    analyzer = WhatIfAnalyzer()
    with pytest.raises(KeyError):
        analyzer.simulate(whatif_repo, 'function:utils.does_not_exist')


def test_whatif_api_and_test_affected(whatif_repo: Path):
    """Test 9, 10: API and Test affected."""
    analyzer = WhatIfAnalyzer()
    result = analyzer.simulate(whatif_repo, 'function:logic.process')
    
    assert len(result.affected_apis) == 1
    assert result.affected_apis[0].route_path == '/data'
    assert result.affected_apis[0].function_name == 'handle_data'
    
    assert len(result.affected_tests) == 1
    assert result.affected_tests[0].test_name == 'test_process'


def test_whatif_circular_dependency(whatif_repo: Path):
    """Test 11: Circular dependency graph."""
    analyzer = WhatIfAnalyzer()
    result = analyzer.simulate(whatif_repo, 'function:circ_a.func_a')
    assert 'module:circ_b' in result.direct_impact
    assert result.blast_radius.total_affected_count > 0


def test_whatif_unresolved_dependency(whatif_repo: Path):
    """Test 13: Repository with unresolved dependencies."""
    analyzer = WhatIfAnalyzer()
    result = analyzer.simulate(whatif_repo, 'function:broken.broken')
    assert 'module:broken' in result.direct_impact
    assert result.blast_radius.total_affected_count > 0


def test_whatif_empty_repository(tmp_path: Path):
    """Test 12: Empty repository."""
    analyzer = WhatIfAnalyzer()
    with pytest.raises(KeyError):
        analyzer.simulate(tmp_path, 'function:main.main')


def test_whatif_risk_and_blast_radius(whatif_repo: Path):
    """Test 14, 15: Risk and Blast Radius calculation."""
    analyzer = WhatIfAnalyzer()
    result = analyzer.simulate(whatif_repo, 'function:utils.format_data')
    
    assert result.predicted_risk_score > 0
    assert result.predicted_risk_level in ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
    assert len(result.risk_contributors) > 0
    assert len(result.recommendations) > 0
    
    br = result.blast_radius
    assert br.direct_impact_count > 0
    assert br.transitive_impact_count > 0
    assert br.affected_api_count > 0
    assert br.affected_test_count > 0


def test_whatif_complexity_and_hotspot(whatif_repo: Path):
    """Test 16: Complexity and hotspot information."""
    analyzer = WhatIfAnalyzer()
    result = analyzer.simulate(whatif_repo, 'function:utils.format_data')
    
    assert result.complexity is not None
    assert 'cyclomatic_complexity' in result.complexity
    assert result.complexity['cyclomatic_complexity'] == 1
    
    # It might not be a hotspot (score < threshold), but the data struct could be None or present.
    # Hotspot is only present if it scores above threshold in analyze_hotspots.
    # In this tiny repo it might be None, which is acceptable.
    # But complexity MUST be present since it's an existing function.


def test_whatif_api_endpoint(client: TestClient, whatif_repo: Path):
    """Test What-If API endpoint."""
    payload = {
        'path': str(whatif_repo),
        'component_id': 'function:logic.process'
    }
    response = client.post('/api/analyze/what-if', json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data['simulation'] is True
    assert data['component_id'] == 'function:logic.process'
    assert data['blast_radius']['affected_api_count'] == 1


def test_whatif_cli_execution(whatif_repo: Path):
    """Test 17, 18: CLI execution and JSON output."""
    import sys
    # python -m app.cli.main what-if <repo> --component function:logic.process --json
    cmd = [
        sys.executable, '-m', 'app.cli.main', 
        'what-if', str(whatif_repo), 
        '--component', 'function:logic.process', 
        '--json'
    ]
    
    # Run from the backend dir so imports work
    backend_dir = Path(__file__).parent.parent
    result = subprocess.run(cmd, cwd=str(backend_dir), capture_output=True, text=True)
    
    assert result.returncode == 0
    
    # Verify JSON output
    data = json.loads(result.stdout)
    assert data['simulation'] is True
    assert data['component_id'] == 'function:logic.process'


def test_whatif_repository_unchanged(whatif_repo: Path):
    """Test 19: Verify repository is unchanged after simulation."""
    import os
    
    # Get state before
    before_files = set(os.listdir(whatif_repo))
    before_mtimes = {f: os.path.getmtime(whatif_repo / f) for f in before_files}
    
    analyzer = WhatIfAnalyzer()
    analyzer.simulate(whatif_repo, 'function:utils.format_data')
    
    # Get state after
    after_files = set(os.listdir(whatif_repo))
    after_mtimes = {f: os.path.getmtime(whatif_repo / f) for f in after_files}
    
    assert before_files == after_files
    assert before_mtimes == after_mtimes
    
    # If there was a .git dir, verify it didn't change (not present in tmp_path, but logic holds)
