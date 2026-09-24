"""API endpoints for repository analysis."""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

def _resolve_repo_path(path_str: str) -> Path:
    """Resolve a local repository path or acquire GitHub URL."""
    if path_str.startswith("http://") or path_str.startswith("https://"):
        from app.services.github_service import GitHubService
        import tempfile
        import shutil
        import atexit
        from git import Repo
        service = GitHubService()
        clean_url = service.validate_url(path_str)
        temp_dir = Path(tempfile.mkdtemp(prefix='scopeguard_auto_'))
        # Register cleanup to avoid completely filling disk, though container restarts help
        atexit.register(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        Repo.clone_from(clean_url, temp_dir)
        return temp_dir
    
    p = Path(path_str)
    if not p.is_absolute():
        p = p.resolve()
    return p

from app.analyzers.dependency_graph import DependencyGraphBuilder
from app.analyzers.history_analyzer import HistoryAnalyzer
from app.analyzers.impact_analyzer import ImpactAnalyzer
from app.analyzers.repository_scanner import RepositoryScanner, RepositoryTooLargeError
from app.analyzers.risk_engine import RiskEngine
from app.analyzers.test_impact_analyzer import TestImpactAnalyzer
from app.analyzers.complexity_analyzer import ComplexityAnalyzer
from app.analyzers.hotspot_analyzer import HotspotAnalyzer
from app.models.analysis_models import AnalyzeRequest, RepositoryAnalysis
from app.models.change_models import CommitAnalysis, CommitAnalyzeRequest
from app.models.graph_models import DependencyAnalysis, ImpactResult
from app.models.history_models import HistoricalAnalysisResult, HistoryAnalyzeRequest
from app.models.risk_models import CommitRiskAnalysis
from app.models.test_models import CommitTestAnalysis
from app.models.complexity_models import ComplexityResult, HotspotResult
from app.models.whatif_models import WhatIfRequest, WhatIfResult
from app.models.pr_models import PRAnalyzeRequest, PRAnalysisResult
from app.analyzers.pr_analyzer import PRAnalyzer

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/api/analyze', tags=['analysis'])

@router.post('/pr', response_model=PRAnalysisResult)
async def analyze_pr(request: PRAnalyzeRequest) -> PRAnalysisResult:
    """Analyze a Pull Request (commit range).

    Compares base and head commits to produce a comprehensive PR risk report,
    including file changes, component impact, test selection, complexity delta,
    and engineering hotspots.

    Args:
        request: PRAnalyzeRequest with repository path, base_commit, and head_commit.

    Returns:
        PRAnalysisResult with the complete analysis.
    """
    repo_path = _resolve_repo_path(request.path)

    logger.info(
        'PR analysis request: %s %s..%s',
        repo_path, request.base_commit, request.head_commit,
    )

    analyzer = PRAnalyzer()

    try:
        result = analyzer.analyze_pr(
            repo_path, request.base_commit, request.head_commit,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RepositoryTooLargeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(
            'Unexpected error during PR analysis: %s', e, exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f'PR analysis failed: {e}',
        )

    return result


from app.services.github_service import GitHubService, InvalidGitHubURLError, RepositoryAcquisitionError
from app.models.analysis_models import GitHubAnalyzeRequest, FullAnalysisResult
from app.analyzers.history_analyzer import HistoryAnalyzer


def _run_full_analysis(repo_path: Path, display_path: str | None = None, history_limit: int = 10) -> FullAnalysisResult:
    """Run the complete ScopeGuard analysis pipeline on a repository.

    Reuses the existing M3-M6 analyzers — no duplicate logic.

    Args:
        repo_path: Path to the (local or temp-cloned) repository.
        display_path: Path/URL to show in the response instead of
                      the actual filesystem path (e.g., the GitHub URL).

    Returns:
        FullAnalysisResult containing risk, test impact, and history.
    """
    show_path = display_path or str(repo_path)

    # M3 + M4: Commit risk analysis (uses existing RiskEngine + ImpactAnalyzer)
    engine = RiskEngine()
    risk_result = engine.analyze_commit_risk(repo_path, 'HEAD')
    risk_result.repository_path = show_path

    # M5: Test impact analysis (uses existing TestImpactAnalyzer)
    test_analyzer = TestImpactAnalyzer()
    test_result = test_analyzer.analyze_commit_tests(repo_path, 'HEAD')
    test_result.repository_path = show_path

    # M6: Historical analysis (uses existing HistoryAnalyzer)
    history_analyzer = HistoryAnalyzer()
    history_result = history_analyzer.analyze_history(repo_path, history_limit)
    history_result.repository_path = show_path

    return FullAnalysisResult(
        risk=risk_result,
        tests=test_result,
        history=history_result,
    )


@router.post('/github', response_model=FullAnalysisResult)
async def analyze_github(request: GitHubAnalyzeRequest) -> FullAnalysisResult:
    """Analyze a remote GitHub repository using the full ScopeGuard pipeline.

    Securely acquires the repository into a transient directory, runs
    the complete M3-M6 analysis pipeline (risk, test impact, history),
    and automatically cleans up the repository upon completion.

    The GitHub integration acts purely as an input acquisition layer —
    all analysis reuses the same RiskEngine, TestImpactAnalyzer, and
    HistoryAnalyzer used for local repositories.

    Args:
        request: GitHubAnalyzeRequest containing the repository URL.

    Returns:
        FullAnalysisResult with risk, test impact, and historical analysis.
    """
    logger.info('GitHub analysis request for: %s', request.url)

    github_service = GitHubService()

    try:
        with github_service.acquire_repository(request.url) as temp_repo_path:
            result = _run_full_analysis(temp_repo_path, display_path=request.url, history_limit=1)
            return result
    except InvalidGitHubURLError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RepositoryTooLargeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RepositoryAcquisitionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error('Unexpected error during GitHub analysis: %s', e, exc_info=True)
        raise HTTPException(status_code=500, detail=f'GitHub analysis failed: {e}')


@router.post('/full', response_model=FullAnalysisResult)
async def analyze_full(request: AnalyzeRequest) -> FullAnalysisResult:
    """Run the full ScopeGuard analysis pipeline on a local repository.

    Runs the complete M3-M6 pipeline (commit risk, test impact, history)
    against the HEAD commit. This is the same pipeline used by the
    GitHub endpoint — the only difference is the repository source.

    Args:
        request: AnalyzeRequest containing the local repository path.

    Returns:
        FullAnalysisResult with risk, test impact, and historical analysis.
    """
    repo_path = _resolve_repo_path(request.path)

    logger.info('Full analysis request for: %s', repo_path)

    try:
        result = _run_full_analysis(repo_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RepositoryTooLargeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error('Unexpected error during full analysis: %s', e, exc_info=True)
        raise HTTPException(status_code=500, detail=f'Full analysis failed: {e}')

    return result


@router.post('/what-if', response_model=WhatIfResult)
async def analyze_what_if(request: WhatIfRequest) -> WhatIfResult:
    """Simulate the impact of changing a component.

    Args:
        request: WhatIfRequest with repository path and component_id.

    Returns:
        WhatIfResult with predicted impact, risk, complexity, and recommendations.
    """
    repo_path = _resolve_repo_path(request.path)

    logger.info('What-If analysis request: %s @ %s', repo_path, request.component_id)

    from app.analyzers.whatif_analyzer import WhatIfAnalyzer
    analyzer = WhatIfAnalyzer()
    
    try:
        result = analyzer.simulate(repo_path, request.component_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error('Unexpected error during what-if analysis: %s', e, exc_info=True)
        raise HTTPException(status_code=500, detail=f'What-If analysis failed: {e}')
        
    return result


@router.post('/repository', response_model=RepositoryAnalysis)
async def analyze_repository(request: AnalyzeRequest) -> RepositoryAnalysis:
    """Analyze a local Python repository.
    
    Accepts a path to a local directory containing Python source files,
    scans the directory, and returns structured analysis results.
    
    Args:
        request: AnalyzeRequest containing the repository path.
        
    Returns:
        RepositoryAnalysis with detailed analysis of all Python files.
        
    Raises:
        HTTPException: 400 if path is invalid, 404 if not found, 500 on error.
    """
    repo_path = _resolve_repo_path(request.path)
    
    logger.info('Received analysis request for: %s', repo_path)
    
    scanner = RepositoryScanner()
    
    try:
        result = scanner.scan(repo_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error('Unexpected error during analysis: %s', e, exc_info=True)
        raise HTTPException(status_code=500, detail=f'Analysis failed: {e}')
    
    return result


@router.post('/dependencies', response_model=DependencyAnalysis)
async def analyze_dependencies(request: AnalyzeRequest) -> DependencyAnalysis:
    """Analyze dependencies in a local Python repository.
    
    Scans the repository, builds a dependency graph, and returns
    structured information about component relationships.
    
    Args:
        request: AnalyzeRequest containing the repository path.
        
    Returns:
        DependencyAnalysis with graph nodes, edges, statistics, and unresolved deps.
    """
    repo_path = _resolve_repo_path(request.path)
    
    logger.info('Received dependency analysis request for: %s', repo_path)
    
    scanner = RepositoryScanner()
    
    try:
        repo_analysis = scanner.scan(repo_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error('Unexpected error during scanning: %s', e, exc_info=True)
        raise HTTPException(status_code=500, detail=f'Scanning failed: {e}')
    
    try:
        graph_builder = DependencyGraphBuilder()
        result = graph_builder.build(repo_analysis)
    except Exception as e:
        logger.error('Unexpected error building dependency graph: %s', e, exc_info=True)
        raise HTTPException(status_code=500, detail=f'Graph construction failed: {e}')
    
    return result


@router.get('/dependencies/{component_id:path}/impact', response_model=ImpactResult)
async def get_component_impact(
    component_id: str,
    repository_path: str,
) -> ImpactResult:
    """Get the impact analysis for a specific component.
    
    Returns direct and transitive dependents of the specified component.
    
    Args:
        component_id: The component ID to analyze (e.g. 'function:payment_service.process_payment').
        repository_path: Path to the repository to analyze.
        
    Returns:
        ImpactResult with direct and transitive dependents.
    """
    repo_path = _resolve_repo_path(repository_path)
    
    logger.info('Impact analysis for %s in %s', component_id, repo_path)
    
    scanner = RepositoryScanner()
    
    try:
        repo_analysis = scanner.scan(repo_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error('Unexpected error during scanning: %s', e, exc_info=True)
        raise HTTPException(status_code=500, detail=f'Scanning failed: {e}')
    
    graph_builder = DependencyGraphBuilder()
    graph_builder.build(repo_analysis)
    
    try:
        impact = graph_builder.get_impact(component_id)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f'Component not found: {component_id}',
        )
    except Exception as e:
        logger.error('Unexpected error during impact analysis: %s', e, exc_info=True)
        raise HTTPException(status_code=500, detail=f'Impact analysis failed: {e}')
    
    return impact


@router.post('/commit', response_model=CommitAnalysis)
async def analyze_commit(request: CommitAnalyzeRequest) -> CommitAnalysis:
    """Analyze a Git commit and its impact on the codebase.

    Given a Git repository path and a commit hash, determines what changed,
    which components are affected, and computes the blast radius.

    Args:
        request: CommitAnalyzeRequest with repository path and commit hash.

    Returns:
        CommitAnalysis with commit info, changed files, changed components,
        direct/transitive impact, affected APIs, and blast radius.
    """
    repo_path = _resolve_repo_path(request.path)

    logger.info(
        'Commit analysis request: %s @ %s', repo_path, request.commit,
    )

    analyzer = ImpactAnalyzer()

    try:
        result = analyzer.analyze_commit(repo_path, request.commit)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(
            'Unexpected error during commit analysis: %s', e, exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f'Commit analysis failed: {e}',
        )

    return result


@router.post('/commit/risk', response_model=CommitRiskAnalysis)
async def analyze_commit_risk(
    request: CommitAnalyzeRequest,
) -> CommitRiskAnalysis:
    """Analyze a Git commit and compute its regression risk score.

    Runs the full M3 commit analysis pipeline, then applies the
    deterministic risk engine to produce a score (0-100), risk level,
    contributing factors, and actionable recommendations.

    The risk score is entirely rule-based — no AI or LLM is used.

    Args:
        request: CommitAnalyzeRequest with repository path and commit hash.

    Returns:
        CommitRiskAnalysis with M3 analysis plus risk assessment.
    """
    repo_path = _resolve_repo_path(request.path)

    logger.info(
        'Commit risk analysis request: %s @ %s', repo_path, request.commit,
    )

    engine = RiskEngine()

    try:
        result = engine.analyze_commit_risk(repo_path, request.commit)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(
            'Unexpected error during risk analysis: %s', e, exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f'Risk analysis failed: {e}',
        )

    return result


@router.post('/commit/tests', response_model=CommitTestAnalysis)
async def analyze_commit_tests(
    request: CommitAnalyzeRequest,
) -> CommitTestAnalysis:
    """Analyze which tests are affected by a Git commit.

    Discovers tests in the repository, maps them to application
    components, and determines which tests should be run based on
    the commit's impact on the dependency graph.

    ScopeGuard NEVER executes tests from the analyzed repository.
    This endpoint only identifies and prioritises affected tests.

    Args:
        request: CommitAnalyzeRequest with repository path and commit hash.

    Returns:
        CommitTestAnalysis with M3 analysis plus test selection.
    """
    repo_path = _resolve_repo_path(request.path)

    logger.info(
        'Test impact analysis request: %s @ %s', repo_path, request.commit,
    )

    analyzer = TestImpactAnalyzer()

    try:
        result = analyzer.analyze_commit_tests(repo_path, request.commit)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(
            'Unexpected error during test analysis: %s', e, exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f'Test analysis failed: {e}',
        )

    return result


@router.post('/history', response_model=HistoricalAnalysisResult)
async def analyze_history(
    request: HistoryAnalyzeRequest,
) -> HistoricalAnalysisResult:
    """Analyze Git history for change patterns and component hotspots.

    Examines recent commits using the M3-M5 pipeline to identify
    component hotspots, risk trends, and frequently affected areas.

    All analysis is read-only and deterministic. Hotspots indicate
    frequently changed components — they do NOT imply bugs or regressions.

    Args:
        request: HistoryAnalyzeRequest with repository path and commit limit.

    Returns:
        HistoricalAnalysisResult with hotspots, risk trends, and insights.
    """
    repo_path = _resolve_repo_path(request.path)

    logger.info(
        'Historical analysis request: %s (limit=%d)',
        repo_path, request.limit,
    )

    analyzer = HistoryAnalyzer()

    try:
        result = analyzer.analyze_history(repo_path, request.limit)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(
            'Unexpected error during historical analysis: %s',
            e, exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f'Historical analysis failed: {e}',
        )

    return result


@router.post('/complexity', response_model=ComplexityResult)
async def analyze_complexity(request: AnalyzeRequest) -> ComplexityResult:
    """Analyze code complexity for a repository.

    Args:
        request: AnalyzeRequest with repository path.

    Returns:
        ComplexityResult with per-function metrics.
    """
    repo_path = _resolve_repo_path(request.path)

    logger.info('Complexity analysis request: %s', repo_path)

    analyzer = ComplexityAnalyzer()
    
    try:
        result = analyzer.analyze_repository(repo_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error('Unexpected error during complexity analysis: %s', e, exc_info=True)
        raise HTTPException(status_code=500, detail=f'Complexity analysis failed: {e}')
        
    return result


@router.post('/hotspots', response_model=HotspotResult)
async def analyze_hotspots(request: AnalyzeRequest) -> HotspotResult:
    """Identify engineering hotspots in a repository.

    Args:
        request: AnalyzeRequest with repository path.

    Returns:
        HotspotResult with identified hotspots and scores.
    """
    repo_path = _resolve_repo_path(request.path)

    logger.info('Hotspot analysis request: %s', repo_path)

    analyzer = HotspotAnalyzer()
    
    try:
        result = analyzer.analyze_hotspots(repo_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error('Unexpected error during hotspot analysis: %s', e, exc_info=True)
        raise HTTPException(status_code=500, detail=f'Hotspot analysis failed: {e}')
        
    return result
