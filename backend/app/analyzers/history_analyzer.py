"""Historical change intelligence analyzer.

Analyzes multiple Git commits to identify component hotspots, risk
trends, change frequency, and frequently affected components.

Reuses M3 (ImpactAnalyzer), M4 (RiskEngine), and M5 (TestImpactAnalyzer)
for per-commit analysis. Does NOT duplicate their logic.

IMPORTANT:
- All analysis is read-only.
- Hotspots indicate frequent/high-impact changes — NOT bugs or regressions.
- Only information derivable from Git history is reported.
- No code from the analyzed repository is ever executed.
"""

import logging
from collections import defaultdict
from pathlib import Path

from app.analyzers.impact_analyzer import ImpactAnalyzer
from app.analyzers.risk_engine import RiskEngine
from app.analyzers.test_impact_analyzer import TestImpactAnalyzer
from app.models.change_models import CommitAnalysis, ComponentChangeType
from app.models.history_models import (
    ComponentHistory,
    FrequentlyAffectedComponent,
    HistoricalAnalysisResult,
    HistoricalCommit,
    RiskTrendPoint,
    RiskTrendSummary,
)
from app.models.risk_models import RiskLevel, RiskScore
from app.models.test_models import TestSelectionResult
from app.services.git_service import GitService

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Hotspot scoring weights — centralised constants
# ------------------------------------------------------------------
_WEIGHT_CHANGE_FREQUENCY: float = 3.0
_WEIGHT_AVG_RISK: float = 1.0
_WEIGHT_AVG_IMPACT: float = 2.0


class HistoryAnalyzer:
    """Analyzes Git history and produces historical change intelligence.

    Reuses existing M3-M5 analyzers for per-commit analysis. Aggregates
    results into hotspots, risk trends, and insights.
    """

    def __init__(self) -> None:
        self._git = GitService()
        self._impact = ImpactAnalyzer()
        self._risk = RiskEngine()
        self._test_impact = TestImpactAnalyzer()

    def analyze_history(
        self, repo_path: Path, limit: int = 20,
    ) -> HistoricalAnalysisResult:
        """Run the full historical analysis pipeline.

        Args:
            repo_path: Path to the Git repository.
            limit: Number of recent commits to analyze (1-100).

        Returns:
            HistoricalAnalysisResult with hotspots, trends, and insights.
        """
        repo = self._git.open_repo(repo_path)
        raw_commits = self._git.get_commit_history(repo, limit)

        logger.info(
            'Analyzing history for %s: %d commits',
            repo_path, len(raw_commits),
        )

        # Per-commit analysis (reuses M3-M5)
        historical_commits: list[HistoricalCommit] = []
        analyses: list[tuple[CommitAnalysis, RiskScore, TestSelectionResult]] = []

        for raw in raw_commits:
            try:
                commit_hash = raw.hexsha
                m3 = self._impact.analyze_commit(repo_path, commit_hash)
                m4 = self._risk.calculate(m3)
                m5 = self._test_impact.analyze_commit_tests(
                    repo_path, commit_hash,
                )
                test_sel = m5.test_selection

                hc = HistoricalCommit(
                    commit_hash=m3.commit.commit_hash,
                    short_hash=m3.commit.short_hash,
                    author=m3.commit.author,
                    message=m3.commit.message,
                    timestamp=m3.commit.timestamp,
                    changed_file_count=len(m3.file_changes),
                    changed_component_count=len(m3.changed_components),
                    direct_impact_count=len(m3.direct_impact),
                    transitive_impact_count=len(m3.transitive_impact),
                    affected_api_count=len(m3.affected_apis),
                    risk_score=m4.score,
                    risk_level=m4.level.value,
                    selected_test_count=test_sel.selected_tests,
                )
                historical_commits.append(hc)
                analyses.append((m3, m4, test_sel))
            except Exception as e:
                logger.warning(
                    'Skipping commit %s: %s', raw.hexsha[:7], e,
                )

        # Chronological order (oldest first) for trends
        historical_commits.reverse()
        analyses.reverse()

        # Build aggregated results
        hotspots = self._build_hotspots(analyses)
        risk_trend = self._build_risk_trend(historical_commits)
        risk_summary = self._build_risk_summary(historical_commits)
        high_risk = [
            hc for hc in historical_commits
            if hc.risk_level in ('HIGH', 'CRITICAL')
        ]
        freq_changed = [h for h in hotspots if h.change_count >= 2]
        freq_affected = self._build_frequently_affected(analyses)
        summary = self._build_summary(historical_commits, risk_summary)
        insights = self._build_insights(
            historical_commits, hotspots, risk_summary, freq_affected,
        )

        return HistoricalAnalysisResult(
            repository_path=str(repo_path),
            graph_basis='current_head',
            commits_analyzed=historical_commits,
            commit_count=len(historical_commits),
            component_hotspots=hotspots,
            risk_trend=risk_trend,
            risk_trend_summary=risk_summary,
            high_risk_commits=high_risk,
            frequently_changed_components=freq_changed,
            frequently_affected_components=freq_affected,
            summary=summary,
            insights=insights,
        )

    # ------------------------------------------------------------------
    # Hotspot aggregation
    # ------------------------------------------------------------------

    def _build_hotspots(
        self,
        analyses: list[tuple[CommitAnalysis, RiskScore, TestSelectionResult]],
    ) -> list[ComponentHistory]:
        """Aggregate per-component change history and compute hotspot scores."""
        comp_data: dict[str, dict] = defaultdict(lambda: {
            'change_count': 0,
            'modification_count': 0,
            'addition_count': 0,
            'removal_count': 0,
            'risk_scores': [],
            'direct_impacts': [],
            'transitive_impacts': [],
        })

        for m3, m4, _ts in analyses:
            for cc in m3.changed_components:
                d = comp_data[cc.component_id]
                d['change_count'] += 1
                if cc.change_type == ComponentChangeType.MODIFIED:
                    d['modification_count'] += 1
                elif cc.change_type == ComponentChangeType.ADDED:
                    d['addition_count'] += 1
                elif cc.change_type == ComponentChangeType.REMOVED:
                    d['removal_count'] += 1
                d['risk_scores'].append(m4.score)
                d['direct_impacts'].append(len(m3.direct_impact))
                d['transitive_impacts'].append(len(m3.transitive_impact))

        hotspots: list[ComponentHistory] = []
        for cid, d in comp_data.items():
            avg_risk = sum(d['risk_scores']) / len(d['risk_scores'])
            max_risk = max(d['risk_scores'])
            avg_impact = (
                (sum(d['direct_impacts']) + sum(d['transitive_impacts']))
                / len(d['risk_scores'])
            )
            hotspot_score = (
                d['change_count'] * _WEIGHT_CHANGE_FREQUENCY
                + avg_risk * _WEIGHT_AVG_RISK
                + avg_impact * _WEIGHT_AVG_IMPACT
            )
            hotspots.append(ComponentHistory(
                component_id=cid,
                change_count=d['change_count'],
                modification_count=d['modification_count'],
                addition_count=d['addition_count'],
                removal_count=d['removal_count'],
                average_risk=round(avg_risk, 1),
                max_risk=max_risk,
                total_direct_impact=sum(d['direct_impacts']),
                total_transitive_impact=sum(d['transitive_impacts']),
                hotspot_score=round(hotspot_score, 1),
            ))

        hotspots.sort(key=lambda h: h.hotspot_score, reverse=True)
        return hotspots

    # ------------------------------------------------------------------
    # Risk trend
    # ------------------------------------------------------------------

    def _build_risk_trend(
        self, commits: list[HistoricalCommit],
    ) -> list[RiskTrendPoint]:
        return [
            RiskTrendPoint(
                commit_hash=hc.short_hash,
                timestamp=hc.timestamp,
                score=hc.risk_score,
                risk_level=hc.risk_level,
            )
            for hc in commits
        ]

    def _build_risk_summary(
        self, commits: list[HistoricalCommit],
    ) -> RiskTrendSummary:
        if not commits:
            return RiskTrendSummary()
        scores = [hc.risk_score for hc in commits]
        levels = [hc.risk_level for hc in commits]
        return RiskTrendSummary(
            average_risk=round(sum(scores) / len(scores), 1),
            highest_risk=max(scores),
            lowest_risk=min(scores),
            low_count=levels.count('LOW'),
            medium_count=levels.count('MEDIUM'),
            high_count=levels.count('HIGH'),
            critical_count=levels.count('CRITICAL'),
        )

    # ------------------------------------------------------------------
    # Frequently affected components
    # ------------------------------------------------------------------

    def _build_frequently_affected(
        self,
        analyses: list[tuple[CommitAnalysis, RiskScore, TestSelectionResult]],
    ) -> list[FrequentlyAffectedComponent]:
        """Find components most frequently appearing in impact results."""
        affected_data: dict[str, dict] = defaultdict(lambda: {
            'count': 0,
            'sources': set(),
        })

        for m3, _m4, _ts in analyses:
            for imp in m3.direct_impact:
                d = affected_data[imp.component_id]
                d['count'] += 1
                d['sources'].update(imp.source_changes)
            for imp in m3.transitive_impact:
                d = affected_data[imp.component_id]
                d['count'] += 1
                d['sources'].update(imp.source_changes)

        result = [
            FrequentlyAffectedComponent(
                component_id=cid,
                times_affected=d['count'],
                source_components=sorted(d['sources']),
            )
            for cid, d in affected_data.items()
            if d['count'] >= 1
        ]
        result.sort(key=lambda f: f.times_affected, reverse=True)
        return result

    # ------------------------------------------------------------------
    # Summary and insights
    # ------------------------------------------------------------------

    def _build_summary(
        self,
        commits: list[HistoricalCommit],
        risk_summary: RiskTrendSummary,
    ) -> str:
        n = len(commits)
        if n == 0:
            return 'No commits analyzed.'
        return (
            f'Analyzed {n} commit{"s" if n != 1 else ""}. '
            f'Average risk: {risk_summary.average_risk}/100. '
            f'Highest risk: {risk_summary.highest_risk}/100. '
            f'{risk_summary.high_count + risk_summary.critical_count} '
            f'commit{"s" if (risk_summary.high_count + risk_summary.critical_count) != 1 else ""} '
            f'classified as HIGH or CRITICAL.'
        )

    def _build_insights(
        self,
        commits: list[HistoricalCommit],
        hotspots: list[ComponentHistory],
        risk_summary: RiskTrendSummary,
        freq_affected: list[FrequentlyAffectedComponent],
    ) -> list[str]:
        insights: list[str] = []
        n = len(commits)

        if n == 0:
            return ['No commits to analyze.']

        # Risk distribution
        if risk_summary.high_count + risk_summary.critical_count > 0:
            insights.append(
                f'{risk_summary.high_count + risk_summary.critical_count} '
                f'of the last {n} analyzed commits were classified as '
                f'HIGH or CRITICAL risk.'
            )

        if risk_summary.low_count == n:
            insights.append(
                f'All {n} analyzed commits had LOW risk scores.'
            )

        # Top hotspots
        for h in hotspots[:3]:
            if h.change_count >= 2:
                insights.append(
                    f'{h.component_id} was changed {h.change_count} '
                    f'times with an average risk of {h.average_risk}.'
                )

        # Frequently affected
        for fa in freq_affected[:3]:
            if fa.times_affected >= 2:
                insights.append(
                    f'{fa.component_id} was affected in '
                    f'{fa.times_affected} commits by changes to: '
                    f'{", ".join(fa.source_components[:3])}.'
                )

        # Average risk
        insights.append(
            f'Average historical risk across {n} commits: '
            f'{risk_summary.average_risk}/100.'
        )

        return insights
