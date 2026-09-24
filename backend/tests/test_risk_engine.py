"""Tests for Milestone 4 — Deterministic Regression Risk Engine.

All tests verify the deterministic, rule-based scoring model.
No AI/LLM is involved.
"""

import textwrap
from pathlib import Path

import git
import pytest

from app.analyzers.risk_engine import RiskEngine
from app.models.change_models import (
    AffectedAPI,
    BlastRadius,
    CommitAnalysis,
    CommitInfo,
    ComponentChange,
    ComponentChangeType,
    FileChange,
    ChangeType,
    ImpactedComponent,
)
from app.models.graph_models import ComponentType
from app.models.risk_models import RiskLevel


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

def _stub_commit() -> CommitInfo:
    return CommitInfo(
        commit_hash='a' * 40,
        short_hash='a' * 7,
        author='Test',
        author_email='test@test.com',
        message='test commit',
        timestamp='2026-01-01T00:00:00+00:00',
        parent_hash='b' * 40,
        changed_file_count=1,
    )


def _make_analysis(
    changed: list[ComponentChange] | None = None,
    direct: list[ImpactedComponent] | None = None,
    transitive: list[ImpactedComponent] | None = None,
    apis: list[AffectedAPI] | None = None,
    file_changes: list[FileChange] | None = None,
) -> CommitAnalysis:
    return CommitAnalysis(
        repository_path='/repo',
        commit=_stub_commit(),
        file_changes=file_changes or [],
        changed_components=changed or [],
        direct_impact=direct or [],
        transitive_impact=transitive or [],
        affected_apis=apis or [],
        blast_radius=BlastRadius(),
    )


def _make_changed(n: int, change_type: ComponentChangeType = ComponentChangeType.MODIFIED) -> list[ComponentChange]:
    return [
        ComponentChange(
            component_id=f'function:mod.func_{i}',
            component_type=ComponentType.FUNCTION,
            change_type=change_type,
            file_path='mod.py',
            name=f'func_{i}',
        )
        for i in range(n)
    ]


def _make_direct(n: int) -> list[ImpactedComponent]:
    return [
        ImpactedComponent(
            component_id=f'module:dep_{i}',
            component_type=ComponentType.MODULE,
            impact_type='direct',
            source_changes=['function:mod.func_0'],
        )
        for i in range(n)
    ]


def _make_transitive(n: int) -> list[ImpactedComponent]:
    return [
        ImpactedComponent(
            component_id=f'module:trans_{i}',
            component_type=ComponentType.MODULE,
            impact_type='transitive',
            source_changes=['function:mod.func_0'],
        )
        for i in range(n)
    ]


def _make_apis(n: int) -> list[AffectedAPI]:
    return [
        AffectedAPI(
            route_path=f'/api/route_{i}',
            http_method='GET',
            function_name=f'handler_{i}',
            file_path='api.py',
            impact_type='direct',
        )
        for i in range(n)
    ]


@pytest.fixture
def engine():
    return RiskEngine()


# ---------------------------------------------------------------
# No changes / minimal change → LOW
# ---------------------------------------------------------------

class TestLowRisk:
    def test_empty_analysis(self, engine):
        analysis = _make_analysis()
        score = engine.calculate(analysis)
        assert score.score == 0
        assert score.level == RiskLevel.LOW

    def test_single_addition(self, engine):
        analysis = _make_analysis(
            changed=_make_changed(1, ComponentChangeType.ADDED),
        )
        score = engine.calculate(analysis)
        assert score.level == RiskLevel.LOW
        assert score.score <= 24

    def test_single_modification_no_impact(self, engine):
        analysis = _make_analysis(
            changed=_make_changed(1, ComponentChangeType.MODIFIED),
        )
        score = engine.calculate(analysis)
        # 5 (1 changed) + 8 (modification) = 13
        assert score.score == 13
        assert score.level == RiskLevel.LOW


# ---------------------------------------------------------------
# Moderate impact → MEDIUM
# ---------------------------------------------------------------

class TestMediumRisk:
    def test_moderate_changes(self, engine):
        analysis = _make_analysis(
            changed=_make_changed(2),
            direct=_make_direct(3),
        )
        score = engine.calculate(analysis)
        # 10 (2-3 changed) + 10 (3-5 direct) + 8 (modifications) = 28
        assert score.level == RiskLevel.MEDIUM

    def test_small_with_apis(self, engine):
        analysis = _make_analysis(
            changed=_make_changed(1),
            direct=_make_direct(1),
            apis=_make_apis(3),
        )
        score = engine.calculate(analysis)
        # 5 + 5 + 10 + 8 = 28
        assert score.level == RiskLevel.MEDIUM


# ---------------------------------------------------------------
# Large impact → HIGH
# ---------------------------------------------------------------

class TestHighRisk:
    def test_large_direct_impact(self, engine):
        analysis = _make_analysis(
            changed=_make_changed(5),
            direct=_make_direct(6),
            transitive=_make_transitive(3),
            apis=_make_apis(4),
        )
        score = engine.calculate(analysis)
        # 15 + 15 + 5 + 10 + 8 + 5 = 58
        assert score.level == RiskLevel.HIGH

    def test_large_transitive(self, engine):
        analysis = _make_analysis(
            changed=_make_changed(3),
            direct=_make_direct(4),
            transitive=_make_transitive(5),
            apis=_make_apis(6),
        )
        score = engine.calculate(analysis)
        # 10 + 10 + 10 + 15 + 8 + 5 = 58
        assert score.level == RiskLevel.HIGH

    def test_api_heavy(self, engine):
        analysis = _make_analysis(
            changed=_make_changed(4),
            direct=_make_direct(5),
            transitive=_make_transitive(4),
            apis=_make_apis(8),
        )
        score = engine.calculate(analysis)
        # 15 + 10 + 10 + 15 + 8 + 5 = 63
        assert score.level == RiskLevel.HIGH


# ---------------------------------------------------------------
# Very large → CRITICAL
# ---------------------------------------------------------------

class TestCriticalRisk:
    def test_massive_change(self, engine):
        analysis = _make_analysis(
            changed=_make_changed(10),
            direct=_make_direct(8),
            transitive=_make_transitive(10),
            apis=_make_apis(12),
        )
        score = engine.calculate(analysis)
        # 20 + 15 + 15 + 15 + 8 + 10 = 83
        assert score.level == RiskLevel.CRITICAL
        assert score.score >= 75


# ---------------------------------------------------------------
# Removal-heavy / mixed change types
# ---------------------------------------------------------------

class TestChangeTypes:
    def test_removal_increases_risk(self, engine):
        removed = _make_changed(1, ComponentChangeType.REMOVED)
        added = _make_changed(1, ComponentChangeType.ADDED)
        score_rem = engine.calculate(_make_analysis(changed=removed))
        score_add = engine.calculate(_make_analysis(changed=added))
        assert score_rem.score > score_add.score

    def test_mixed_types_highest(self, engine):
        mixed = [
            ComponentChange(
                component_id='function:m.a', component_type=ComponentType.FUNCTION,
                change_type=ComponentChangeType.ADDED, file_path='m.py', name='a',
            ),
            ComponentChange(
                component_id='function:m.b', component_type=ComponentType.FUNCTION,
                change_type=ComponentChangeType.MODIFIED, file_path='m.py', name='b',
            ),
            ComponentChange(
                component_id='function:m.c', component_type=ComponentType.FUNCTION,
                change_type=ComponentChangeType.REMOVED, file_path='m.py', name='c',
            ),
        ]
        score = engine.calculate(_make_analysis(changed=mixed))
        # Mixed type = 12 points (highest change-type score)
        factors_by_name = {f.name: f for f in score.factors}
        assert factors_by_name['change_types'].points == 12


# ---------------------------------------------------------------
# Score cap and thresholds
# ---------------------------------------------------------------

class TestScoreMechanics:
    def test_score_capped_at_100(self, engine):
        # Stack everything to max
        analysis = _make_analysis(
            changed=_make_changed(20),
            direct=_make_direct(20),
            transitive=_make_transitive(20),
            apis=_make_apis(20),
        )
        score = engine.calculate(analysis)
        assert score.score <= 100

    def test_threshold_low_boundary(self, engine):
        assert RiskEngine._level_from_score(0) == RiskLevel.LOW
        assert RiskEngine._level_from_score(24) == RiskLevel.LOW

    def test_threshold_medium_boundary(self, engine):
        assert RiskEngine._level_from_score(25) == RiskLevel.MEDIUM
        assert RiskEngine._level_from_score(49) == RiskLevel.MEDIUM

    def test_threshold_high_boundary(self, engine):
        assert RiskEngine._level_from_score(50) == RiskLevel.HIGH
        assert RiskEngine._level_from_score(74) == RiskLevel.HIGH

    def test_threshold_critical_boundary(self, engine):
        assert RiskEngine._level_from_score(75) == RiskLevel.CRITICAL
        assert RiskEngine._level_from_score(100) == RiskLevel.CRITICAL


# ---------------------------------------------------------------
# Risk factors correctness
# ---------------------------------------------------------------

class TestRiskFactors:
    def test_factors_have_descriptions(self, engine):
        analysis = _make_analysis(
            changed=_make_changed(2),
            direct=_make_direct(1),
        )
        score = engine.calculate(analysis)
        for f in score.factors:
            assert f.description
            assert f.points > 0

    def test_correct_changed_component_points(self, engine):
        for n, expected in [(1, 5), (3, 10), (5, 15), (8, 20)]:
            analysis = _make_analysis(changed=_make_changed(n))
            score = engine.calculate(analysis)
            by_name = {f.name: f for f in score.factors}
            assert by_name['changed_components'].points == expected, (
                f'n={n}, expected={expected}'
            )

    def test_correct_direct_impact_points(self, engine):
        for n, expected in [(1, 5), (4, 10), (7, 15)]:
            analysis = _make_analysis(
                changed=_make_changed(1, ComponentChangeType.ADDED),
                direct=_make_direct(n),
            )
            score = engine.calculate(analysis)
            by_name = {f.name: f for f in score.factors}
            assert by_name['direct_impact'].points == expected

    def test_zero_factors_excluded(self, engine):
        analysis = _make_analysis(changed=_make_changed(1))
        score = engine.calculate(analysis)
        for f in score.factors:
            assert f.points > 0


# ---------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------

class TestRecommendations:
    def test_low_has_recommendations(self, engine):
        score = engine.calculate(_make_analysis(changed=_make_changed(1)))
        assert len(score.recommendations) > 0

    def test_critical_has_many_recommendations(self, engine):
        analysis = _make_analysis(
            changed=_make_changed(10),
            direct=_make_direct(10),
            transitive=_make_transitive(10),
            apis=_make_apis(10),
        )
        score = engine.calculate(analysis)
        assert len(score.recommendations) >= 3

    def test_medium_mentions_review(self, engine):
        analysis = _make_analysis(
            changed=_make_changed(2),
            direct=_make_direct(3),
        )
        score = engine.calculate(analysis)
        recs_text = ' '.join(score.recommendations).lower()
        assert 'review' in recs_text or 'test' in recs_text

    def test_critical_mentions_regression(self, engine):
        analysis = _make_analysis(
            changed=_make_changed(10),
            direct=_make_direct(10),
            transitive=_make_transitive(10),
            apis=_make_apis(10),
        )
        score = engine.calculate(analysis)
        recs_text = ' '.join(score.recommendations).lower()
        assert 'regression' in recs_text


# ---------------------------------------------------------------
# Summary
# ---------------------------------------------------------------

class TestSummary:
    def test_summary_contains_score(self, engine):
        analysis = _make_analysis(changed=_make_changed(2))
        score = engine.calculate(analysis)
        assert str(score.score) in score.summary
        assert score.level.value in score.summary


# ---------------------------------------------------------------
# Git repo fixtures for integration tests
# ---------------------------------------------------------------

def _init_repo(path: Path) -> git.Repo:
    repo = git.Repo.init(str(path))
    repo.config_writer().set_value('user', 'name', 'Test').release()
    repo.config_writer().set_value('user', 'email', 'test@test.com').release()
    return repo


@pytest.fixture
def integration_repo(tmp_path):
    """Multi-module repo for integration testing."""
    repo = _init_repo(tmp_path)

    (tmp_path / 'service.py').write_text(textwrap.dedent('''\
        from helper import do_work

        def serve():
            return do_work()
    '''))
    (tmp_path / 'helper.py').write_text(textwrap.dedent('''\
        def do_work():
            return 1
    '''))
    repo.git.add(A=True)
    repo.index.commit('Initial')

    (tmp_path / 'helper.py').write_text(textwrap.dedent('''\
        def do_work():
            return 42
    '''))
    repo.git.add(A=True)
    repo.index.commit('Modify do_work')

    return tmp_path


# ---------------------------------------------------------------
# Integration: RiskEngine.analyze_commit_risk
# ---------------------------------------------------------------

class TestIntegration:
    def test_analyze_commit_risk(self, integration_repo):
        engine = RiskEngine()
        result = engine.analyze_commit_risk(integration_repo, 'HEAD')
        assert result.risk.score >= 0
        assert result.risk.level in list(RiskLevel)
        assert result.commit.message == 'Modify do_work'
        assert len(result.changed_components) >= 1


# ---------------------------------------------------------------
# API endpoint integration
# ---------------------------------------------------------------

class TestRiskEndpoint:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_risk_endpoint_success(self, client, integration_repo):
        r = client.post('/api/analyze/commit/risk', json={
            'path': str(integration_repo),
            'commit': 'HEAD',
        })
        assert r.status_code == 200
        data = r.json()
        assert 'risk' in data
        assert 'score' in data['risk']
        assert 'level' in data['risk']
        assert 'factors' in data['risk']
        assert 'recommendations' in data['risk']
        # M3 fields still present
        assert 'commit' in data
        assert 'changed_components' in data
        assert 'blast_radius' in data

    def test_risk_endpoint_invalid_commit(self, client, integration_repo):
        r = client.post('/api/analyze/commit/risk', json={
            'path': str(integration_repo),
            'commit': 'deadbeef' * 5,
        })
        assert r.status_code == 400

    def test_risk_endpoint_invalid_path(self, client):
        r = client.post('/api/analyze/commit/risk', json={
            'path': '/nonexistent',
            'commit': 'HEAD',
        })
        assert r.status_code in (400, 404)

    def test_existing_commit_endpoint_unchanged(self, client, integration_repo):
        """Verify the original M3 endpoint still works."""
        r = client.post('/api/analyze/commit', json={
            'path': str(integration_repo),
            'commit': 'HEAD',
        })
        assert r.status_code == 200
        data = r.json()
        assert 'risk' not in data  # M3 endpoint does NOT include risk
        assert 'commit' in data
        assert 'blast_radius' in data
