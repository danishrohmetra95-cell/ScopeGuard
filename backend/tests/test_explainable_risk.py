"""Tests for the explainable RiskEngine."""

from app.analyzers.risk_engine import RiskEngine
from app.models.change_models import (
    AffectedAPI,
    BlastRadius,
    CommitAnalysis,
    CommitInfo,
    ComponentChange,
    ComponentChangeType,
    FileChange,
    ImpactedComponent,
)
from app.models.risk_models import RiskLevel

def test_risk_score_determinism_and_explainability():
    """Verify risk scores match the baseline and explainability is populated."""
    engine = RiskEngine()

    # Create a mock analysis scenario that hits multiple factors
    analysis = CommitAnalysis(
        repository_path='/fake/repo',
        commit=CommitInfo(commit_hash='123', short_hash='123', author='a', author_email='a@b.com', message='m', timestamp='d'),
        file_changes=[FileChange(path='a.py', change_type='modified', additions=10, deletions=5)],
        changed_components=[
            ComponentChange(component_id='comp_a', component_type='function', name='a', file_path='a.py', change_type=ComponentChangeType.MODIFIED),
            ComponentChange(component_id='comp_b', component_type='function', name='b', file_path='b.py', change_type=ComponentChangeType.REMOVED),
        ],
        direct_impact=[
            ImpactedComponent(component_id='dep_1', component_type='function', impact_type='direct'),
            ImpactedComponent(component_id='dep_2', component_type='function', impact_type='direct'),
            ImpactedComponent(component_id='dep_3', component_type='function', impact_type='direct'),
            ImpactedComponent(component_id='dep_4', component_type='function', impact_type='direct'),
        ],
        transitive_impact=[
            ImpactedComponent(component_id='trans_1', component_type='function', impact_type='transitive'),
            ImpactedComponent(component_id='trans_2', component_type='function', impact_type='transitive'),
        ],
        affected_apis=[
            AffectedAPI(route_path='/api/v1/test', http_method='GET', file_path='api.py', function_name='test', impact_type='direct'),
        ],
        blast_radius=BlastRadius()
    )

    # Expected calculation based on rules:
    # 2 components changed (2-3 threshold) = 10 points
    # 4 direct dependents (3-5 threshold) = 10 points
    # 2 transitive dependents (1-3 threshold) = 5 points
    # 1 affected API (1-2 threshold) = 5 points
    # Change types (Modified, Removed) (Removals threshold) = 10 points (Actually Mixed because >= 2? Let's check logic: has_modified and has_removed -> count = 2 -> MIXED -> 12 points)
    # Dependency depth: 2 transitive dependents (moderate <= 5) = 5 points
    # Total points expected: 10 + 10 + 5 + 5 + 12 + 5 = 47 points

    score = engine.calculate(analysis)

    # 1. Assert score and level remain deterministic
    assert score.score == 47
    assert score.level == RiskLevel.MEDIUM

    # 2. Assert explainability breakdown is fully populated
    breakdown = score.contributor_breakdown
    assert len(breakdown) == 6

    # Convert breakdown to dict for easy assertions
    b_map = {c.name: c for c in breakdown}

    # Changed components
    assert b_map['changed_components'].measured_value == 2
    assert b_map['changed_components'].rule == '2-3 components'
    assert set(b_map['changed_components'].evidence) == {'comp_a', 'comp_b'}

    # Direct impact
    assert b_map['direct_impact'].measured_value == 4
    assert b_map['direct_impact'].rule == '3-5 dependents'
    assert 'dep_1' in b_map['direct_impact'].evidence

    # Transitive impact
    assert b_map['transitive_impact'].measured_value == 2
    assert b_map['transitive_impact'].rule == '1-3 dependents'

    # APIs
    assert b_map['affected_apis'].measured_value == 1
    assert b_map['affected_apis'].rule == '1-2 APIs'
    assert b_map['affected_apis'].evidence == ['/api/v1/test']

    # Change types
    assert b_map['change_types'].measured_value == 'Mixed'
    assert b_map['change_types'].rule == 'Mixed changes'
    assert 'modified' in b_map['change_types'].evidence
    assert 'removed' in b_map['change_types'].evidence

    # Depth
    assert b_map['dependency_depth'].measured_value == 2
    assert b_map['dependency_depth'].rule == '1-5 transitive dependents'

    # Recommendations
    recs = score.recommendations
    assert len(recs) > 0

def test_risk_score_zero_impact():
    engine = RiskEngine()
    analysis = CommitAnalysis(
        repository_path='/fake/repo',
        commit=CommitInfo(commit_hash='123', short_hash='123', author='a', author_email='a@b.com', message='m', timestamp='d'),
        file_changes=[],
        changed_components=[],
        direct_impact=[],
        transitive_impact=[],
        affected_apis=[],
        blast_radius=BlastRadius()
    )

    score = engine.calculate(analysis)
    assert score.score == 0
    assert score.level == RiskLevel.LOW
    
    # All factors have 0 points, so they are not included in the active contributor breakdown
    assert len(score.contributor_breakdown) == 0

def test_risk_score_critical_impact():
    engine = RiskEngine()
    analysis = CommitAnalysis(
        repository_path='/fake/repo',
        commit=CommitInfo(commit_hash='123', short_hash='123', author='a', author_email='a@b.com', message='m', timestamp='d'),
        file_changes=[],
        changed_components=[ComponentChange(component_id=f'c_{i}', component_type='function', name=f'c_{i}', file_path='a.py', change_type=ComponentChangeType.MODIFIED) for i in range(10)],
        direct_impact=[ImpactedComponent(component_id=f'd_{i}', component_type='function', impact_type='direct') for i in range(10)],
        transitive_impact=[ImpactedComponent(component_id=f't_{i}', component_type='function', impact_type='transitive') for i in range(15)],
        affected_apis=[AffectedAPI(route_path=f'/api/v1/{i}', http_method='GET', file_path='api.py', function_name='test', impact_type='direct') for i in range(10)],
        blast_radius=BlastRadius()
    )

    # 10 components (7+) = 20
    # 10 direct (6+) = 15
    # 15 transitive (9+) = 15
    # 10 apis (6+) = 15
    # only modifications = 8
    # 15 depth (deep) = 10
    # total = 20 + 15 + 15 + 15 + 8 + 10 = 83

    score = engine.calculate(analysis)
    assert score.score == 83
    assert score.level == RiskLevel.CRITICAL

    breakdown = score.contributor_breakdown
    assert len(breakdown) == 6
    b_map = {c.name: c for c in breakdown}
    assert b_map['changed_components'].rule == '7+ components'
    assert b_map['dependency_depth'].rule == '6+ transitive dependents'
    assert len(b_map['changed_components'].evidence) == 10
