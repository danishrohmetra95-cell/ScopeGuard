"""Tests for code complexity and hotspot analysis."""

import textwrap
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.analyzers.complexity_analyzer import ComplexityAnalyzer
from app.analyzers.hotspot_analyzer import HotspotAnalyzer
from app.analyzers.repository_scanner import RepositoryScanner
from app.analyzers.dependency_graph import DependencyGraphBuilder
from app.models.complexity_models import ComplexityRating
from app.main import app


@pytest.fixture
def complex_repo(tmp_path: Path) -> Path:
    """A repository with varying levels of complexity."""
    # Simple function (Complexity 1)
    (tmp_path / 'simple.py').write_text(textwrap.dedent('''
        def add(a, b):
            return a + b
    ''').lstrip())

    # Branching (Complexity 3: 1 + if + elif)
    (tmp_path / 'branching.py').write_text(textwrap.dedent('''
        def check_value(x):
            if x > 10:
                return "high"
            elif x < 0:
                return "negative"
            else:
                return "normal"
    ''').lstrip())

    # Loops and nesting (Complexity 5: 1 + for + if + while + if)
    (tmp_path / 'loops.py').write_text(textwrap.dedent('''
        def process_items(items):
            for item in items:
                if item.valid:
                    n = 5
                    while n > 0:
                        if n % 2 == 0:
                            print(n)
                        n -= 1
    ''').lstrip())

    # High complexity (Complexity > 10)
    (tmp_path / 'high_complex.py').write_text(textwrap.dedent('''
        class Processor:
            def complex_method(self, data):
                result = []
                for item in data:
                    if item == 1:
                        result.append("one")
                    elif item == 2:
                        result.append("two")
                    elif item == 3:
                        result.append("three")
                    elif item == 4:
                        result.append("four")
                    elif item == 5:
                        result.append("five")
                    elif item == 6:
                        result.append("six")
                    else:
                        if isinstance(item, list):
                            for sub in item:
                                if sub > 0:
                                    result.append(sub)
                                elif sub < 0:
                                    pass
                        elif isinstance(item, dict):
                            for k, v in item.items():
                                if v:
                                    result.append(k)
                return result
    ''').lstrip())
    
    # Syntax error
    (tmp_path / 'syntax_err.py').write_text('def bad():\n  if a == 1\n    pass\n')
    
    return tmp_path


def test_complexity_analyzer(complex_repo: Path):
    """Test cyclomatic complexity calculation and metrics."""
    analyzer = ComplexityAnalyzer()
    result = analyzer.analyze_repository(complex_repo)

    assert result.repository_path == str(complex_repo)
    assert result.summary.total_functions == 4
    
    # Function lookups
    funcs = {f.name: f for f in result.functions}
    
    # simple.add
    add = funcs['add']
    assert add.cyclomatic_complexity == 1
    assert add.lines_of_code == 2
    assert add.parameter_count == 2
    assert add.rating == ComplexityRating.LOW
    assert not add.is_method
    
    # branching.check_value
    check_value = funcs['check_value']
    assert check_value.cyclomatic_complexity == 3
    assert check_value.branch_count == 2
    assert check_value.max_nesting_depth == 2
    
    # loops.process_items
    process = funcs['process_items']
    assert process.cyclomatic_complexity == 5
    assert process.loop_count == 2
    assert process.branch_count == 2
    assert process.max_nesting_depth == 4
    
    # high_complex.complex_method
    complex_method = funcs['complex_method']
    assert complex_method.cyclomatic_complexity >= 11
    assert complex_method.rating in (ComplexityRating.HIGH, ComplexityRating.VERY_HIGH)
    assert complex_method.is_method
    assert complex_method.parameter_count == 1  # 'self' is excluded


def test_hotspot_analyzer(complex_repo: Path):
    """Test hotspot calculation integrating complexity, dependency, and frequency."""
    analyzer = HotspotAnalyzer()
    
    # Mock change frequency
    history = {
        'function:simple.add': 5,
        'method:high_complex.Processor.complex_method': 12,
    }
    
    result = analyzer.analyze_hotspots(complex_repo, change_frequency=history)
    
    # Should identify components
    assert len(result.hotspots) > 0
    
    # Find specific hotspots
    hotspots = {h.component_id: h for h in result.hotspots}
    
    # high_complex method should have high complexity score and high change frequency
    complex_hotspot = hotspots.get('method:high_complex.Processor.complex_method')
    assert complex_hotspot is not None
    assert complex_hotspot.complexity_score > 0
    assert complex_hotspot.change_frequency_score > 0
    assert len(complex_hotspot.reasons) >= 2


def test_api_complexity(client: TestClient, tmp_repo: Path):
    """Test the /api/analyze/complexity endpoint."""
    response = client.post('/api/analyze/complexity', json={'path': str(tmp_repo)})
    assert response.status_code == 200
    data = response.json()
    assert 'functions' in data
    assert 'summary' in data
    assert data['summary']['total_functions'] > 0


def test_api_hotspots(client: TestClient, tmp_repo: Path):
    """Test the /api/analyze/hotspots endpoint."""
    response = client.post('/api/analyze/hotspots', json={'path': str(tmp_repo)})
    assert response.status_code == 200
    data = response.json()
    assert 'hotspots' in data
    assert 'methodology' in data


def test_empty_repository(tmp_path: Path):
    """Test analyzers with an empty repository."""
    analyzer = ComplexityAnalyzer()
    result = analyzer.analyze_repository(tmp_path)
    assert result.summary.total_functions == 0
    
    h_analyzer = HotspotAnalyzer()
    h_result = h_analyzer.analyze_hotspots(tmp_path)
    assert len(h_result.hotspots) == 0


def test_circular_dependency_hotspot(tmp_path: Path):
    """Test hotspot analysis on circular dependencies."""
    (tmp_path / 'a.py').write_text('from b import b_func\ndef a_func():\n    b_func()\n')
    (tmp_path / 'b.py').write_text('from a import a_func\ndef b_func():\n    a_func()\n')
    
    h_analyzer = HotspotAnalyzer()
    result = h_analyzer.analyze_hotspots(tmp_path)
    # Circular dependencies shouldn't crash it, should just add to dependency score
    assert len(result.hotspots) > 0
