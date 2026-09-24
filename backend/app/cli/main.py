"""ScopeGuard CLI — command-line interface for code change impact analysis.

Usage:
    python -m app.cli.main analyze <repository>
    python -m app.cli.main risk <repository> [--commit COMMIT] [--threshold N] [--json]
    python -m app.cli.main tests <repository> [--commit COMMIT] [--json]
    python -m app.cli.main history <repository> [--limit N] [--json]
"""

import argparse
import json
import sys
from pathlib import Path


def _validate_repo(path_str: str) -> Path:
    """Validate and return the repository path."""
    repo_path = Path(path_str)
    if not repo_path.is_absolute():
        repo_path = repo_path.resolve()
    if not repo_path.exists():
        print(f'Error: Path does not exist: {repo_path}', file=sys.stderr)
        sys.exit(1)
    if not repo_path.is_dir():
        print(f'Error: Not a directory: {repo_path}', file=sys.stderr)
        sys.exit(1)
    return repo_path


def cmd_analyze(args: argparse.Namespace) -> None:
    """Run repository analysis (M1)."""
    from app.analyzers.repository_scanner import RepositoryScanner

    repo_path = _validate_repo(args.repository)
    scanner = RepositoryScanner()

    try:
        result = scanner.scan(repo_path)
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        print(f'Repository: {result.repository_path}')
        print(f'Total files: {result.summary.total_files}')
        print(f'Total functions: {result.summary.total_functions}')
        print(f'Total classes: {result.summary.total_classes}')
        for fa in result.files:
            print(f'  {fa.file_path} — {len(fa.functions)} functions, {len(fa.classes)} classes')


def cmd_risk(args: argparse.Namespace) -> None:
    """Run commit risk analysis (M3+M4)."""
    from app.analyzers.risk_engine import RiskEngine
    from app.reporting.report_generator import generate_risk_report

    repo_path = _validate_repo(args.repository)
    engine = RiskEngine()

    try:
        result = engine.analyze_commit_risk(repo_path, args.commit)
    except FileNotFoundError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    if args.json:
        report = generate_risk_report(result)
        print(json.dumps(report, indent=2))
    else:
        print(f'Commit: {result.commit.short_hash} by {result.commit.author}')
        print(f'Message: {result.commit.message}')
        print(f'\nRisk Score: {result.risk.score}/100')
        print(f'Risk Level: {result.risk.level.value}')
        print(f'Summary: {result.risk.summary}')
        if result.risk.contributor_breakdown:
            print('\nRisk Breakdown (Explainable):')
            for c in result.risk.contributor_breakdown:
                print(f'  • {c.human_label}: +{c.points} pts ({c.percentage}%)')
                if c.measured_value is not None:
                    print(f'    - Measured: {c.measured_value} (Rule: {c.rule})')
                if c.evidence:
                    for ev in c.evidence[:3]:
                        print(f'      - {ev}')
                    if len(c.evidence) > 3:
                        print(f'      ... and {len(c.evidence)-3} more')
        elif result.risk.factors:
            print('\nRisk Factors:')
            for f in result.risk.factors:
                print(f'  [{f.severity.upper()}] {f.name}: +{f.points} — {f.description}')
        if result.risk.recommendations:
            print('\nRecommendations:')
            for i, rec in enumerate(result.risk.recommendations, 1):
                print(f'  {i}. {rec}')
        print(f'\nBlast Radius:')
        br = result.blast_radius
        print(f'  Changed files: {br.changed_file_count}')
        print(f'  Changed components: {br.changed_component_count}')
        print(f'  Direct impact: {br.direct_impact_count}')
        print(f'  Transitive impact: {br.transitive_impact_count}')
        print(f'  Total affected: {br.total_affected_count}')
        print(f'  Affected APIs: {br.affected_api_count}')

    # Risk gating: exit with code 2 if threshold exceeded
    threshold = args.threshold
    if threshold is not None and result.risk.score > threshold:
        print(
            f'\nRISK GATE FAILED: score {result.risk.score} exceeds threshold {threshold}',
            file=sys.stderr,
        )
        sys.exit(2)


def cmd_tests(args: argparse.Namespace) -> None:
    """Run test impact analysis (M3+M5)."""
    from app.analyzers.test_impact_analyzer import TestImpactAnalyzer
    from app.reporting.report_generator import generate_test_report

    repo_path = _validate_repo(args.repository)
    analyzer = TestImpactAnalyzer()

    try:
        result = analyzer.analyze_commit_tests(repo_path, args.commit)
    except FileNotFoundError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    if args.json:
        report = generate_test_report(result)
        print(json.dumps(report, indent=2))
    else:
        ts = result.test_selection
        print(f'Commit: {result.commit.short_hash} by {result.commit.author}')
        print(f'\nTest Selection:')
        print(f'  Total tests: {ts.total_tests}')
        print(f'  Selected: {ts.selected_tests}')
        print(f'  Skipped: {ts.skipped_tests}')
        print(f'  Selection: {ts.selection_percentage:.1f}%')
        if ts.high_priority:
            print(f'\n  HIGH priority ({len(ts.high_priority)}):')
            for t in ts.high_priority:
                print(f'    {t.test.test_id}')
                print(f'      Reason: {t.reason}')
        if ts.medium_priority:
            print(f'\n  MEDIUM priority ({len(ts.medium_priority)}):')
            for t in ts.medium_priority:
                print(f'    {t.test.test_id}')
                print(f'      Reason: {t.reason}')
        if ts.low_priority:
            print(f'\n  LOW priority ({len(ts.low_priority)}):')
            for t in ts.low_priority:
                print(f'    {t.test.test_id}')


def cmd_history(args: argparse.Namespace) -> None:
    """Run historical analysis (M6)."""
    from app.analyzers.history_analyzer import HistoryAnalyzer

    repo_path = _validate_repo(args.repository)
    analyzer = HistoryAnalyzer()

    try:
        result = analyzer.analyze_history(repo_path, args.limit)
    except FileNotFoundError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        print(f'Repository: {result.repository_path}')
        print(f'Commits analyzed: {result.commit_count}')
        print(f'Summary: {result.summary}')
        rts = result.risk_trend_summary
        print(f'\nRisk Distribution:')
        print(f'  Average risk: {rts.average_risk:.1f}')
        print(f'  Highest risk: {rts.highest_risk}')
        print(f'  LOW: {rts.low_count}  MEDIUM: {rts.medium_count}  HIGH: {rts.high_count}  CRITICAL: {rts.critical_count}')
        if result.component_hotspots:
            print(f'\nTop Component Hotspots:')
            for h in result.component_hotspots[:5]:
                print(f'  {h.component_id}: {h.change_count} changes, avg risk {h.average_risk:.1f}, hotspot score {h.hotspot_score:.1f}')
        if result.insights:
            print(f'\nInsights:')
            for insight in result.insights:
                print(f'  • {insight}')


def cmd_complexity(args: argparse.Namespace) -> None:
    """Run code complexity analysis."""
    from app.analyzers.complexity_analyzer import ComplexityAnalyzer

    repo_path = _validate_repo(args.repository)
    analyzer = ComplexityAnalyzer()

    try:
        result = analyzer.analyze_repository(repo_path)
    except FileNotFoundError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        print(f'Repository: {result.repository_path}')
        print(f'Total functions: {result.summary.total_functions}')
        print(f'Average complexity: {result.summary.average_complexity}')
        print(f'Max complexity: {result.summary.max_complexity}')
        print(f'\nTop 5 most complex functions:')
        for fc in result.most_complex[:5]:
            print(f'  {fc.component_id}: {fc.cyclomatic_complexity} (Rating: {fc.rating.value})')


def cmd_hotspots(args: argparse.Namespace) -> None:
    """Run engineering hotspot analysis."""
    from app.analyzers.hotspot_analyzer import HotspotAnalyzer

    repo_path = _validate_repo(args.repository)
    analyzer = HotspotAnalyzer()

    try:
        result = analyzer.analyze_hotspots(repo_path)
    except FileNotFoundError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        print(f'Repository: {result.repository_path}')
        print(f'Hotspots found: {result.hotspot_count}')
        print(f'\nTop 5 Hotspots:')
        for h in result.hotspots[:5]:
            print(f'  {h.component_id}: Score {h.hotspot_score}')
            for r in h.reasons:
                print(f'    - {r.description}')


def cmd_whatif(args: argparse.Namespace) -> None:
    """Run What-If impact simulation."""
    from app.analyzers.whatif_analyzer import WhatIfAnalyzer

    repo_path = _validate_repo(args.repository)
    analyzer = WhatIfAnalyzer()

    try:
        result = analyzer.simulate(repo_path, args.component)
    except FileNotFoundError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
    except KeyError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        print(f'Repository: {result.repository_path}')
        print(f'Component: {result.component_id} ({result.component_type})')
        print(f'\n--- WHAT-IF SIMULATION ---')
        print(f'Disclaimer: {result.disclaimer}\n')
        
        br = result.blast_radius
        print(f'Blast Radius:')
        print(f'  Direct dependents: {br.direct_impact_count}')
        print(f'  Transitive dependents: {br.transitive_impact_count}')
        print(f'  Total affected components: {br.total_affected_count}')
        print(f'  Affected APIs: {br.affected_api_count}')
        print(f'  Affected Tests: {br.affected_test_count}')
        
        print(f'\nPredicted Risk: {result.predicted_risk_score}/100 ({result.predicted_risk_level})')
        if result.risk and result.risk.contributor_breakdown:
            print('\nRisk Breakdown (Explainable):')
            for c in result.risk.contributor_breakdown:
                print(f'  • {c.human_label}: +{c.points} pts ({c.percentage}%)')
                if c.measured_value is not None:
                    print(f'    - Measured: {c.measured_value} (Rule: {c.rule})')
                if c.evidence:
                    for ev in c.evidence[:3]:
                        print(f'      - {ev}')
                    if len(c.evidence) > 3:
                        print(f'      ... and {len(c.evidence)-3} more')
        
        if result.complexity:
            print(f'\nComplexity Metrics:')
            print(f'  Cyclomatic Complexity: {result.complexity.get("cyclomatic_complexity")}')
            print(f'  Max Nesting Depth: {result.complexity.get("max_nesting_depth")}')
            
        if result.hotspot:
            print(f'\nHotspot Analysis:')
            print(f'  Hotspot Score: {result.hotspot.get("hotspot_score")}')


def cmd_pr(args: argparse.Namespace) -> None:
    """Run Pull Request analysis."""
    from app.analyzers.pr_analyzer import PRAnalyzer

    repo_path = _validate_repo(args.repository)
    analyzer = PRAnalyzer()

    try:
        result = analyzer.analyze_pr(repo_path, args.base, args.head)
    except FileNotFoundError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        print(f'Repository: {result.repository_path}')
        print(f'PR: {result.base_commit.short_hash} -> {result.head_commit.short_hash}')
        print(f'File Changes: +{result.total_additions} -{result.total_deletions}')
        print(f'\n--- PR RISK REPORT ---')
        
        br = result.blast_radius
        print(f'Blast Radius:')
        print(f'  Changed components: {br.changed_component_count}')
        print(f'  Direct impact: {br.direct_impact_count}')
        print(f'  Transitive impact: {br.transitive_impact_count}')
        print(f'  Affected APIs: {br.affected_api_count}')
        
        ts = result.test_selection
        print(f'\nTest Impact:')
        print(f'  Total tests: {ts.total_tests}')
        print(f'  Selected to run: {ts.selected_tests} ({ts.selection_percentage:.1f}%)')
        print(f'  High priority: {len(ts.high_priority)}')
        print(f'  Medium priority: {len(ts.medium_priority)}')
        
        cd = result.complexity_delta
        print(f'\nComplexity Delta:')
        print(f'  Before: {cd.average_complexity_before} (avg)')
        print(f'  After:  {cd.average_complexity_after} (avg)')
        print(f'  Change: {cd.complexity_change_percentage:+.1f}%')
        
        print(f'\nHotspots Touched: {result.hotspot_count}')
        for h in result.hotspots_touched:
            print(f'  - {h}')
        
        r = result.risk
        print(f'\nOverall Risk Score: {r.score}/100 ({r.level.value})')
        print(f'Summary: {r.summary}')
        if r.contributor_breakdown:
            print('\nRisk Breakdown (Explainable):')
            for c in r.contributor_breakdown:
                print(f'  • {c.human_label}: +{c.points} pts ({c.percentage}%)')
                if c.measured_value is not None:
                    print(f'    - Measured: {c.measured_value} (Rule: {c.rule})')
                if c.evidence:
                    for ev in c.evidence[:3]:
                        print(f'      - {ev}')
                    if len(c.evidence) > 3:
                        print(f'      ... and {len(c.evidence)-3} more')


def cmd_github(args: argparse.Namespace) -> None:
    """Analyze a remote GitHub repository (M1)."""
    from app.services.github_service import GitHubService, GitHubIntegrationError
    from app.analyzers.repository_scanner import RepositoryScanner

    github_service = GitHubService()
    
    try:
        with github_service.acquire_repository(args.url) as temp_repo_path:
            scanner = RepositoryScanner()
            result = scanner.scan(temp_repo_path)
            # Map back to original URL
            result.repository_path = args.url
            
            if args.json:
                print(result.model_dump_json(indent=2))
            else:
                print(f'Repository URL: {result.repository_path}')
                print(f'Total files: {result.summary.total_files}')
                print(f'Total functions: {result.summary.total_functions}')
                print(f'Total classes: {result.summary.total_classes}')
                for fa in result.files:
                    print(f'  {fa.file_path} — {len(fa.functions)} functions, {len(fa.classes)} classes')
                    
    except GitHubIntegrationError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog='scopeguard',
        description='ScopeGuard — Intelligent Code Change Impact & Regression Risk Analysis',
    )
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # analyze
    p_analyze = subparsers.add_parser('analyze', help='Analyze repository structure')
    p_analyze.add_argument('repository', help='Path to the Git repository')
    p_analyze.add_argument('--json', action='store_true', help='Output JSON')
    p_analyze.set_defaults(func=cmd_analyze)

    # github
    p_github = subparsers.add_parser('github', help='Analyze a GitHub repository')
    p_github.add_argument('url', help='GitHub repository URL')
    p_github.add_argument('--json', action='store_true', help='Output JSON')
    p_github.set_defaults(func=cmd_github)

    # risk
    p_risk = subparsers.add_parser('risk', help='Analyze commit risk')
    p_risk.add_argument('repository', help='Path to the Git repository')
    p_risk.add_argument('--commit', default='HEAD', help='Commit hash (default: HEAD)')
    p_risk.add_argument('--threshold', type=int, default=None,
                        help='Risk threshold (exit 2 if score exceeds)')
    p_risk.add_argument('--json', action='store_true', help='Output JSON')
    p_risk.set_defaults(func=cmd_risk)

    # tests
    p_tests = subparsers.add_parser('tests', help='Analyze test impact')
    p_tests.add_argument('repository', help='Path to the Git repository')
    p_tests.add_argument('--commit', default='HEAD', help='Commit hash (default: HEAD)')
    p_tests.add_argument('--json', action='store_true', help='Output JSON')
    p_tests.set_defaults(func=cmd_tests)

    # history
    p_history = subparsers.add_parser('history', help='Analyze change history')
    p_history.add_argument('repository', help='Path to the Git repository')
    p_history.add_argument('--limit', type=int, default=20,
                           help='Max commits to analyze (default: 20)')
    p_history.add_argument('--json', action='store_true', help='Output JSON')
    p_history.set_defaults(func=cmd_history)

    # complexity
    p_complexity = subparsers.add_parser('complexity', help='Analyze code complexity')
    p_complexity.add_argument('repository', help='Path to the Git repository')
    p_complexity.add_argument('--json', action='store_true', help='Output JSON')
    p_complexity.set_defaults(func=cmd_complexity)

    # hotspots
    p_hotspots = subparsers.add_parser('hotspots', help='Analyze engineering hotspots')
    p_hotspots.add_argument('repository', help='Path to the Git repository')
    p_hotspots.add_argument('--json', action='store_true', help='Output JSON')
    p_hotspots.set_defaults(func=cmd_hotspots)

    # what-if
    p_whatif = subparsers.add_parser('what-if', help='Simulate impact of changing a component')
    p_whatif.add_argument('repository', help='Path to the Git repository')
    p_whatif.add_argument('--component', required=True, help='Component ID to simulate (e.g. function:module.func)')
    p_whatif.add_argument('--json', action='store_true', help='Output JSON')
    p_whatif.set_defaults(func=cmd_whatif)

    # pr
    p_pr = subparsers.add_parser('pr', help='Analyze Pull Request risk')
    p_pr.add_argument('repository', help='Path to the Git repository')
    p_pr.add_argument('--base', required=True, help='Base commit hash')
    p_pr.add_argument('--head', required=True, help='Head commit hash')
    p_pr.add_argument('--json', action='store_true', help='Output JSON')
    p_pr.set_defaults(func=cmd_pr)

    return parser


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == '__main__':
    main()
