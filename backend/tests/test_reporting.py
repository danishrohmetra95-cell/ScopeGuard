"""Tests for JSON reporting."""

from datetime import datetime, timezone

from app.models.change_models import CommitInfo
from app.models.risk_models import CommitRiskAnalysis, RiskScore, RiskLevel
from app.models.test_models import CommitTestAnalysis, TestSelectionResult
from app.reporting.report_generator import generate_risk_report, generate_test_report


def _create_mock_commit():
    return CommitInfo(
        commit_hash="fakehash",
        short_hash="fake",
        author="Tester",
        author_email="test@example.com",
        message="Test commit",
        timestamp=datetime.now(timezone.utc).isoformat(),
        parent_hash="parent",
        changed_file_count=1
    )


def test_generate_risk_report():
    """Test JSON risk report generation."""
    analysis = CommitRiskAnalysis(
        repository_path="/fake/path",
        commit=_create_mock_commit(),
        risk=RiskScore(score=45, level=RiskLevel.MEDIUM, summary="Moderate risk")
    )

    report = generate_risk_report(analysis)

    assert report["report_type"] == "risk_analysis"
    assert report["generator"] == "ScopeGuard"
    assert report["repository_path"] == "/fake/path"
    assert report["risk"]["score"] == 45
    assert report["risk"]["level"] == "MEDIUM"
    assert "generated_at" in report


def test_generate_test_report():
    """Test JSON test impact report generation."""
    analysis = CommitTestAnalysis(
        repository_path="/fake/path",
        commit=_create_mock_commit(),
        test_selection=TestSelectionResult(
            total_tests=100,
            selected_tests=10,
            skipped_tests=90,
            selection_percentage=10.0
        )
    )

    report = generate_test_report(analysis)

    assert report["report_type"] == "test_impact"
    assert report["test_selection"]["total_tests"] == 100
    assert report["test_selection"]["selection_percentage"] == 10.0
