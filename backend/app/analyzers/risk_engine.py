"""Deterministic regression risk engine.

Calculates a risk score (0-100) from measurable engineering signals
produced by the M3 commit analysis pipeline. The score is entirely
rule-based — no AI or LLM is used.

Scoring model:
    A. Changed components     — volume of changed code
    B. Direct impact          — immediately dependent components
    C. Transitive impact      — indirectly reachable components
    D. Affected APIs          — user-facing surface area
    E. Change types           — nature of the change (add/modify/remove)
    F. Dependency depth       — depth of transitive chains

Risk levels:
    0-24   LOW
    25-49  MEDIUM
    50-74  HIGH
    75-100 CRITICAL
"""

import logging
from pathlib import Path

from app.analyzers.impact_analyzer import ImpactAnalyzer
from app.models.change_models import (
    CommitAnalysis,
    ComponentChangeType,
)
from app.models.risk_models import (
    CommitRiskAnalysis,
    RiskFactor,
    RiskLevel,
    RiskScore,
)

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Scoring constants — centralised weights and thresholds
# ------------------------------------------------------------------

# A. Changed components
_CHANGED_1: int = 5
_CHANGED_2_3: int = 10
_CHANGED_4_6: int = 15
_CHANGED_7_PLUS: int = 20

# B. Direct impact
_DIRECT_1_2: int = 5
_DIRECT_3_5: int = 10
_DIRECT_6_PLUS: int = 15

# C. Transitive impact
_TRANSITIVE_1_3: int = 5
_TRANSITIVE_4_8: int = 10
_TRANSITIVE_9_PLUS: int = 15

# D. Affected APIs
_API_1_2: int = 5
_API_3_5: int = 10
_API_6_PLUS: int = 15

# E. Change types
_CHANGE_ADDITIONS_ONLY: int = 3
_CHANGE_MODIFICATIONS: int = 8
_CHANGE_REMOVALS: int = 10
_CHANGE_MIXED: int = 12

# F. Dependency depth
_DEPTH_MODERATE: int = 5   # transitive impact 1-5
_DEPTH_DEEP: int = 10      # transitive impact 6+

# Risk level thresholds
_LEVEL_LOW_MAX: int = 24
_LEVEL_MEDIUM_MAX: int = 49
_LEVEL_HIGH_MAX: int = 74
# 75-100 = CRITICAL

_MAX_SCORE: int = 100


# ------------------------------------------------------------------
# Risk engine
# ------------------------------------------------------------------

class RiskEngine:
    """Deterministic regression risk calculator.

    Accepts a CommitAnalysis (from M3) and returns a RiskScore with
    transparent, explainable factors and actionable recommendations.
    """

    def calculate(self, analysis: CommitAnalysis) -> RiskScore:
        """Calculate risk score from commit analysis signals.

        Args:
            analysis: M3 CommitAnalysis containing changed components,
                      impact, blast radius, and affected APIs.

        Returns:
            RiskScore with score, level, factors, summary, and
            recommendations.
        """
        factors: list[RiskFactor] = []

        # A. Changed components
        factors.append(self._score_changed_components(analysis))

        # B. Direct impact
        factors.append(self._score_direct_impact(analysis))

        # C. Transitive impact
        factors.append(self._score_transitive_impact(analysis))

        # D. Affected APIs
        factors.append(self._score_affected_apis(analysis))

        # E. Change types
        factors.append(self._score_change_types(analysis))

        # F. Dependency depth
        factors.append(self._score_dependency_depth(analysis))

        # Remove zero-point factors for cleaner output
        active_factors = [f for f in factors if f.points > 0]

        raw_score = sum(f.points for f in factors)
        score = min(raw_score, _MAX_SCORE)
        level = self._level_from_score(score)
        summary = self._build_summary(score, level, analysis)
        recommendations = self._build_recommendations(level, active_factors)

        from app.models.risk_models import RiskContributor
        contributors: list[RiskContributor] = []
        for f in active_factors:
            percentage = round((f.points / raw_score) * 100, 1) if raw_score > 0 else 0.0
            human_label = f.name.replace('_', ' ').title()
            contributors.append(RiskContributor(
                name=f.name,
                human_label=human_label,
                points=f.points,
                percentage=percentage,
                description=f.description,
                measured_value=f.measured_value,
                rule=f.rule,
                evidence=f.evidence
            ))
            
        # Sort contributors by highest percentage
        contributors.sort(key=lambda c: c.percentage, reverse=True)

        return RiskScore(
            score=score,
            level=level,
            factors=active_factors,
            summary=summary,
            recommendations=recommendations,
            contributor_breakdown=contributors,
        )

    def analyze_commit_risk(
        self, repo_path: Path, commit_hash: str,
    ) -> CommitRiskAnalysis:
        """Run the full M3 pipeline and compute risk.

        Convenience method that runs ImpactAnalyzer then RiskEngine.
        """
        impact_analyzer = ImpactAnalyzer()
        analysis = impact_analyzer.analyze_commit(repo_path, commit_hash)
        risk = self.calculate(analysis)

        return CommitRiskAnalysis(
            repository_path=analysis.repository_path,
            commit=analysis.commit,
            file_changes=analysis.file_changes,
            changed_components=analysis.changed_components,
            direct_impact=analysis.direct_impact,
            transitive_impact=analysis.transitive_impact,
            affected_apis=analysis.affected_apis,
            blast_radius=analysis.blast_radius,
            risk=risk,
        )

    # ------------------------------------------------------------------
    # Factor scorers
    # ------------------------------------------------------------------

    def _score_changed_components(self, analysis: CommitAnalysis) -> RiskFactor:
        n = len(analysis.changed_components)
        evidence = [c.component_id for c in analysis.changed_components]
        if n == 0:
            return RiskFactor(
                name='changed_components', points=0,
                description='No components changed.',
                measured_value=0, rule="0 components", evidence=[]
            )
        if n == 1:
            pts, sev, rule = _CHANGED_1, 'info', "1 component"
        elif n <= 3:
            pts, sev, rule = _CHANGED_2_3, 'info', "2-3 components"
        elif n <= 6:
            pts, sev, rule = _CHANGED_4_6, 'warning', "4-6 components"
        else:
            pts, sev, rule = _CHANGED_7_PLUS, 'critical', "7+ components"
        return RiskFactor(
            name='changed_components', points=pts, severity=sev,
            description=(
                f'{n} component{"s" if n != 1 else ""} changed, '
                f'increasing regression exposure.'
            ),
            measured_value=n, rule=rule, evidence=evidence
        )

    def _score_direct_impact(self, analysis: CommitAnalysis) -> RiskFactor:
        n = len(analysis.direct_impact)
        evidence = [d.component_id for d in analysis.direct_impact]
        if n == 0:
            return RiskFactor(
                name='direct_impact', points=0,
                description='No direct dependents affected.',
                measured_value=0, rule="0 dependents", evidence=[]
            )
        if n <= 2:
            pts, sev, rule = _DIRECT_1_2, 'info', "1-2 dependents"
        elif n <= 5:
            pts, sev, rule = _DIRECT_3_5, 'warning', "3-5 dependents"
        else:
            pts, sev, rule = _DIRECT_6_PLUS, 'critical', "6+ dependents"
        return RiskFactor(
            name='direct_impact', points=pts, severity=sev,
            description=(
                f'{n} component{"s" if n != 1 else ""} directly '
                f'depend{"" if n == 1 else ""} on the changed code.'
            ),
            measured_value=n, rule=rule, evidence=evidence
        )

    def _score_transitive_impact(self, analysis: CommitAnalysis) -> RiskFactor:
        n = len(analysis.transitive_impact)
        evidence = [t.component_id for t in analysis.transitive_impact]
        if n == 0:
            return RiskFactor(
                name='transitive_impact', points=0,
                description='No transitive dependents affected.',
                measured_value=0, rule="0 dependents", evidence=[]
            )
        if n <= 3:
            pts, sev, rule = _TRANSITIVE_1_3, 'info', "1-3 dependents"
        elif n <= 8:
            pts, sev, rule = _TRANSITIVE_4_8, 'warning', "4-8 dependents"
        else:
            pts, sev, rule = _TRANSITIVE_9_PLUS, 'critical', "9+ dependents"
        return RiskFactor(
            name='transitive_impact', points=pts, severity=sev,
            description=(
                f'{n} component{"s" if n != 1 else ""} are transitively '
                f'affected through dependency chains.'
            ),
            measured_value=n, rule=rule, evidence=evidence
        )

    def _score_affected_apis(self, analysis: CommitAnalysis) -> RiskFactor:
        n = len(analysis.affected_apis)
        evidence = [a.route_path for a in analysis.affected_apis if a.route_path]
        if n == 0:
            return RiskFactor(
                name='affected_apis', points=0,
                description='No API routes affected.',
                measured_value=0, rule="0 APIs", evidence=[]
            )
        if n <= 2:
            pts, sev, rule = _API_1_2, 'info', "1-2 APIs"
        elif n <= 5:
            pts, sev, rule = _API_3_5, 'warning', "3-5 APIs"
        else:
            pts, sev, rule = _API_6_PLUS, 'critical', "6+ APIs"
        return RiskFactor(
            name='affected_apis', points=pts, severity=sev,
            description=(
                f'{n} API route{"s" if n != 1 else ""} may be affected '
                f'by this change.'
            ),
            measured_value=n, rule=rule, evidence=evidence
        )

    def _score_change_types(self, analysis: CommitAnalysis) -> RiskFactor:
        types = {cc.change_type for cc in analysis.changed_components}
        evidence = sorted(list({cc.change_type.value for cc in analysis.changed_components}))
        if not types:
            return RiskFactor(
                name='change_types', points=0,
                description='No component changes detected.',
                measured_value="None", rule="No changes", evidence=[]
            )

        has_added = ComponentChangeType.ADDED in types
        has_modified = ComponentChangeType.MODIFIED in types
        has_removed = ComponentChangeType.REMOVED in types

        type_count = sum([has_added, has_modified, has_removed])

        if type_count >= 2:
            pts, sev, rule, val = _CHANGE_MIXED, 'warning', "Mixed changes", "Mixed"
            desc = (
                'Mixed change types (additions, modifications, and/or '
                'removals) increase regression risk.'
            )
        elif has_removed:
            pts, sev, rule, val = _CHANGE_REMOVALS, 'warning', "Removals", "Removed"
            desc = (
                'At least one component was removed, increasing '
                'regression risk for dependents.'
            )
        elif has_modified:
            pts, sev, rule, val = _CHANGE_MODIFICATIONS, 'info', "Modifications", "Modified"
            desc = 'Existing components were modified.'
        else:
            pts, sev, rule, val = _CHANGE_ADDITIONS_ONLY, 'info', "Additions only", "Added"
            desc = (
                'Only new components were added — lowest change-type risk.'
            )

        return RiskFactor(
            name='change_types', points=pts, severity=sev,
            description=desc,
            measured_value=val, rule=rule, evidence=evidence
        )

    def _score_dependency_depth(self, analysis: CommitAnalysis) -> RiskFactor:
        n_transitive = len(analysis.transitive_impact)
        evidence = [t.component_id for t in analysis.transitive_impact]
        if n_transitive == 0:
            return RiskFactor(
                name='dependency_depth', points=0,
                description='No transitive dependency impact.',
                measured_value=0, rule="0 dependents", evidence=[]
            )
        if n_transitive <= 5:
            pts, sev, rule = _DEPTH_MODERATE, 'info', "1-5 transitive dependents"
            desc = (
                f'Moderate dependency depth: {n_transitive} transitive '
                f'dependent{"s" if n_transitive != 1 else ""}.'
            )
        else:
            pts, sev, rule = _DEPTH_DEEP, 'warning', "6+ transitive dependents"
            desc = (
                f'Deep dependency chain: {n_transitive} transitive '
                f'dependents indicate wide blast radius.'
            )
        return RiskFactor(
            name='dependency_depth', points=pts, severity=sev,
            description=desc,
            measured_value=n_transitive, rule=rule, evidence=evidence
        )

    # ------------------------------------------------------------------
    # Level, summary, recommendations
    # ------------------------------------------------------------------

    @staticmethod
    def _level_from_score(score: int) -> RiskLevel:
        if score <= _LEVEL_LOW_MAX:
            return RiskLevel.LOW
        if score <= _LEVEL_MEDIUM_MAX:
            return RiskLevel.MEDIUM
        if score <= _LEVEL_HIGH_MAX:
            return RiskLevel.HIGH
        return RiskLevel.CRITICAL

    @staticmethod
    def _build_summary(
        score: int, level: RiskLevel, analysis: CommitAnalysis,
    ) -> str:
        n_changed = len(analysis.changed_components)
        n_direct = len(analysis.direct_impact)
        n_transitive = len(analysis.transitive_impact)
        n_apis = len(analysis.affected_apis)

        return (
            f'Risk score {score}/100 ({level.value}). '
            f'{n_changed} component{"s" if n_changed != 1 else ""} changed, '
            f'{n_direct} direct and {n_transitive} transitive dependents '
            f'affected, {n_apis} API route{"s" if n_apis != 1 else ""} '
            f'potentially impacted.'
        )

    @staticmethod
    def _build_recommendations(
        level: RiskLevel, factors: list[RiskFactor],
    ) -> list[str]:
        recs: list[str] = []

        if level == RiskLevel.LOW:
            recs.append('Run the relevant unit tests before merging.')

        elif level == RiskLevel.MEDIUM:
            recs.append('Run affected component tests.')
            recs.append('Review directly dependent components.')
            if any(f.name == 'affected_apis' for f in factors):
                recs.append('Verify affected API endpoints.')

        elif level == RiskLevel.HIGH:
            recs.append('Run all affected tests before merging.')
            recs.append('Review the dependency impact before deployment.')
            recs.append('Consider additional regression testing.')
            if any(f.name == 'affected_apis' for f in factors):
                recs.append('Verify all affected API endpoints.')

        elif level == RiskLevel.CRITICAL:
            recs.append('Run the complete regression test suite.')
            recs.append('Require manual code review before merging.')
            recs.append(
                'Review all affected APIs and dependent components.',
            )
            recs.append(
                'Avoid production deployment until regression testing passes.',
            )

        return recs
