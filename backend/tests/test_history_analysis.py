"""Tests for Milestone 6 — Historical Change Intelligence.

All tests use temporary local Git repositories.
Hotspots do NOT imply bugs or regressions.
"""

import textwrap
from pathlib import Path

import git
import pytest

from app.analyzers.history_analyzer import HistoryAnalyzer
from app.services.git_service import GitService


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

def _init_repo(path: Path) -> git.Repo:
    repo = git.Repo.init(str(path))
    repo.config_writer().set_value('user', 'name', 'Test').release()
    repo.config_writer().set_value('user', 'email', 'test@test.com').release()
    return repo


def _commit(repo: git.Repo, msg: str):
    repo.git.add(A=True)
    return repo.index.commit(msg)


# ---------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------

@pytest.fixture
def git_service():
    return GitService()


@pytest.fixture
def history_repo(tmp_path):
    """Repository with multiple meaningful commits."""
    repo = _init_repo(tmp_path)

    # Commit 1: initial
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
    _commit(repo, 'Initial application')

    # Commit 2: modify core
    (tmp_path / 'core.py').write_text(textwrap.dedent('''\
        def compute():
            return 99
    '''))
    _commit(repo, 'Change compute return value')

    # Commit 3: modify service
    (tmp_path / 'service.py').write_text(textwrap.dedent('''\
        from core import compute
        def serve():
            result = compute()
            return result * 2
    '''))
    _commit(repo, 'Double service result')

    # Commit 4: modify core again
    (tmp_path / 'core.py').write_text(textwrap.dedent('''\
        def compute():
            return 100
    '''))
    _commit(repo, 'Round compute to 100')

    # Commit 5: add new function
    (tmp_path / 'core.py').write_text(textwrap.dedent('''\
        def compute():
            return 100
        def validate(x):
            return x > 0
    '''))
    _commit(repo, 'Add validate function')

    return tmp_path


@pytest.fixture
def single_commit_repo(tmp_path):
    repo = _init_repo(tmp_path)
    (tmp_path / 'main.py').write_text('x = 1\n')
    _commit(repo, 'Initial')
    return tmp_path


# ---------------------------------------------------------------
# Git history retrieval
# ---------------------------------------------------------------

class TestGitHistory:
    def test_retrieves_commits(self, git_service, history_repo):
        repo = git_service.open_repo(history_repo)
        commits = git_service.get_commit_history(repo, limit=20)
        assert len(commits) == 5

    def test_commit_metadata(self, git_service, history_repo):
        repo = git_service.open_repo(history_repo)
        commits = git_service.get_commit_history(repo, limit=20)
        for c in commits:
            assert c.hexsha
            assert c.message

    def test_configurable_limit(self, git_service, history_repo):
        repo = git_service.open_repo(history_repo)
        commits = git_service.get_commit_history(repo, limit=2)
        assert len(commits) == 2

    def test_max_limit_100(self, git_service, history_repo):
        repo = git_service.open_repo(history_repo)
        commits = git_service.get_commit_history(repo, limit=200)
        # Clamped to 100, but repo only has 5
        assert len(commits) == 5

    def test_empty_repo(self, tmp_path, git_service):
        repo = _init_repo(tmp_path)
        commits = git_service.get_commit_history(repo, limit=10)
        assert len(commits) == 0


# ---------------------------------------------------------------
# Historical commit analysis
# ---------------------------------------------------------------

class TestHistoricalAnalysis:
    def test_analyzes_all_commits(self, history_repo):
        analyzer = HistoryAnalyzer()
        result = analyzer.analyze_history(history_repo, limit=20)
        # The initial commit may or may not produce changes depending on analysis
        assert result.commit_count >= 4

    def test_commit_fields(self, history_repo):
        analyzer = HistoryAnalyzer()
        result = analyzer.analyze_history(history_repo, limit=20)
        for hc in result.commits_analyzed:
            assert hc.commit_hash
            assert hc.short_hash
            assert hc.author
            assert hc.message
            assert hc.timestamp

    def test_risk_scores_present(self, history_repo):
        analyzer = HistoryAnalyzer()
        result = analyzer.analyze_history(history_repo, limit=20)
        for hc in result.commits_analyzed:
            assert 0 <= hc.risk_score <= 100
            assert hc.risk_level in ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')

    def test_chronological_order(self, history_repo):
        analyzer = HistoryAnalyzer()
        result = analyzer.analyze_history(history_repo, limit=20)
        timestamps = [hc.timestamp for hc in result.commits_analyzed]
        assert timestamps == sorted(timestamps)


# ---------------------------------------------------------------
# Component hotspots
# ---------------------------------------------------------------

class TestHotspots:
    def test_hotspots_exist(self, history_repo):
        analyzer = HistoryAnalyzer()
        result = analyzer.analyze_history(history_repo, limit=20)
        assert len(result.component_hotspots) > 0

    def test_change_frequency(self, history_repo):
        analyzer = HistoryAnalyzer()
        result = analyzer.analyze_history(history_repo, limit=20)
        # core.compute was changed multiple times
        core_hotspot = next(
            (h for h in result.component_hotspots
             if 'compute' in h.component_id),
            None,
        )
        assert core_hotspot is not None
        assert core_hotspot.change_count >= 2

    def test_average_risk(self, history_repo):
        analyzer = HistoryAnalyzer()
        result = analyzer.analyze_history(history_repo, limit=20)
        for h in result.component_hotspots:
            assert 0 <= h.average_risk <= 100

    def test_max_risk(self, history_repo):
        analyzer = HistoryAnalyzer()
        result = analyzer.analyze_history(history_repo, limit=20)
        for h in result.component_hotspots:
            assert h.max_risk >= h.average_risk

    def test_sorted_by_hotspot_score(self, history_repo):
        analyzer = HistoryAnalyzer()
        result = analyzer.analyze_history(history_repo, limit=20)
        scores = [h.hotspot_score for h in result.component_hotspots]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------
# Risk trend
# ---------------------------------------------------------------

class TestRiskTrend:
    def test_trend_points(self, history_repo):
        analyzer = HistoryAnalyzer()
        result = analyzer.analyze_history(history_repo, limit=20)
        assert len(result.risk_trend) == result.commit_count

    def test_trend_ordering(self, history_repo):
        analyzer = HistoryAnalyzer()
        result = analyzer.analyze_history(history_repo, limit=20)
        timestamps = [p.timestamp for p in result.risk_trend]
        assert timestamps == sorted(timestamps)

    def test_risk_summary(self, history_repo):
        analyzer = HistoryAnalyzer()
        result = analyzer.analyze_history(history_repo, limit=20)
        s = result.risk_trend_summary
        assert s.lowest_risk <= s.average_risk <= s.highest_risk
        total = s.low_count + s.medium_count + s.high_count + s.critical_count
        assert total == result.commit_count


# ---------------------------------------------------------------
# Frequently affected components
# ---------------------------------------------------------------

class TestFrequentlyAffected:
    def test_affected_present(self, history_repo):
        analyzer = HistoryAnalyzer()
        result = analyzer.analyze_history(history_repo, limit=20)
        assert len(result.frequently_affected_components) > 0

    def test_source_tracking(self, history_repo):
        analyzer = HistoryAnalyzer()
        result = analyzer.analyze_history(history_repo, limit=20)
        for fa in result.frequently_affected_components:
            if fa.times_affected > 0:
                assert len(fa.source_components) > 0


# ---------------------------------------------------------------
# Insights
# ---------------------------------------------------------------

class TestInsights:
    def test_insights_generated(self, history_repo):
        analyzer = HistoryAnalyzer()
        result = analyzer.analyze_history(history_repo, limit=20)
        assert len(result.insights) > 0

    def test_insights_are_strings(self, history_repo):
        analyzer = HistoryAnalyzer()
        result = analyzer.analyze_history(history_repo, limit=20)
        for insight in result.insights:
            assert isinstance(insight, str)
            assert len(insight) > 10

    def test_no_duplicates(self, history_repo):
        analyzer = HistoryAnalyzer()
        result = analyzer.analyze_history(history_repo, limit=20)
        hashes = [hc.commit_hash for hc in result.commits_analyzed]
        assert len(hashes) == len(set(hashes))


# ---------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------

class TestEdgeCases:
    def test_single_commit(self, single_commit_repo):
        analyzer = HistoryAnalyzer()
        result = analyzer.analyze_history(single_commit_repo, limit=10)
        assert result.commit_count >= 1

    def test_limit_validation(self, history_repo):
        analyzer = HistoryAnalyzer()
        result = analyzer.analyze_history(history_repo, limit=2)
        assert result.commit_count <= 2

    def test_invalid_repo(self, tmp_path):
        analyzer = HistoryAnalyzer()
        with pytest.raises(FileNotFoundError):
            analyzer.analyze_history(tmp_path / 'nonexistent', limit=10)


# ---------------------------------------------------------------
# API endpoint
# ---------------------------------------------------------------

class TestHistoryEndpoint:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_endpoint_success(self, client, history_repo):
        r = client.post('/api/analyze/history', json={
            'path': str(history_repo),
            'limit': 20,
        })
        assert r.status_code == 200
        data = r.json()
        assert 'commits_analyzed' in data
        assert 'component_hotspots' in data
        assert 'risk_trend' in data
        assert 'risk_trend_summary' in data
        assert 'frequently_affected_components' in data
        assert 'insights' in data
        assert 'summary' in data

    def test_endpoint_with_limit(self, client, history_repo):
        r = client.post('/api/analyze/history', json={
            'path': str(history_repo),
            'limit': 2,
        })
        assert r.status_code == 200
        assert r.json()['commit_count'] <= 2

    def test_endpoint_invalid_path(self, client):
        r = client.post('/api/analyze/history', json={
            'path': '/nonexistent',
            'limit': 5,
        })
        assert r.status_code in (400, 404)

    def test_existing_endpoints_unchanged(self, client, history_repo):
        """Verify M3, M4, M5 endpoints still work."""
        r3 = client.post('/api/analyze/commit', json={
            'path': str(history_repo),
            'commit': 'HEAD',
        })
        assert r3.status_code == 200
        assert 'test_selection' not in r3.json()

        r4 = client.post('/api/analyze/commit/risk', json={
            'path': str(history_repo),
            'commit': 'HEAD',
        })
        assert r4.status_code == 200
        assert 'risk' in r4.json()
