"""Structured JSON report generation for ScopeGuard.

All reports are built by serializing existing Pydantic models from the
M1-M6 analysis pipeline. No analysis logic is duplicated here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _meta() -> dict[str, Any]:
    """Common report metadata."""
    return {
        'generator': 'ScopeGuard',
        'version': '0.8.0',
        'generated_at': datetime.now(timezone.utc).isoformat(),
    }


def generate_risk_report(result) -> dict[str, Any]:
    """Generate a JSON risk report from a CommitRiskAnalysis.

    Reuses the Pydantic model's serialization.
    """
    data = result.model_dump()
    return {
        **_meta(),
        'report_type': 'risk_analysis',
        'repository_path': data['repository_path'],
        'commit': data['commit'],
        'file_changes': data['file_changes'],
        'changed_components': data['changed_components'],
        'direct_impact': data['direct_impact'],
        'transitive_impact': data['transitive_impact'],
        'affected_apis': data.get('affected_apis', []),
        'blast_radius': data['blast_radius'],
        'risk': data['risk'],
    }


def generate_test_report(result) -> dict[str, Any]:
    """Generate a JSON test-impact report from a CommitTestAnalysis.

    Reuses the Pydantic model's serialization.
    """
    data = result.model_dump()
    return {
        **_meta(),
        'report_type': 'test_impact',
        'repository_path': data['repository_path'],
        'commit': data['commit'],
        'file_changes': data['file_changes'],
        'changed_components': data['changed_components'],
        'direct_impact': data['direct_impact'],
        'transitive_impact': data['transitive_impact'],
        'blast_radius': data['blast_radius'],
        'test_selection': data['test_selection'],
    }


def generate_full_report(risk_result, test_result, history_result=None) -> dict[str, Any]:
    """Generate a combined report merging risk, test, and optional history data."""
    risk_data = risk_result.model_dump()
    test_data = test_result.model_dump()

    report = {
        **_meta(),
        'report_type': 'full_analysis',
        'repository_path': risk_data['repository_path'],
        'commit': risk_data['commit'],
        'file_changes': risk_data['file_changes'],
        'changed_components': risk_data['changed_components'],
        'direct_impact': risk_data['direct_impact'],
        'transitive_impact': risk_data['transitive_impact'],
        'affected_apis': risk_data.get('affected_apis', []),
        'blast_radius': risk_data['blast_radius'],
        'risk': risk_data['risk'],
        'test_selection': test_data['test_selection'],
    }

    if history_result is not None:
        history_data = history_result.model_dump()
        report['history'] = {
            'commits_analyzed': history_data['commits_analyzed'],
            'risk_trend_summary': history_data['risk_trend_summary'],
            'component_hotspots': history_data['component_hotspots'],
            'insights': history_data['insights'],
        }

    return report
