"""Static code complexity analyzer using Python AST.

Calculates per-function complexity metrics without executing any code.
Reuses the existing ASTAnalyzer infrastructure for file discovery
and the DependencyGraphBuilder for graph-based metrics.

Cyclomatic complexity is calculated by counting decision points:
    - if / elif
    - for / while
    - except
    - with
    - assert
    - boolean operators (and / or)
    - conditional expressions (ternary)
    - comprehension if-clauses

Base complexity is 1 (a function with no branches has complexity 1).
"""

import ast
import logging
import statistics
from pathlib import Path

from app.analyzers.repository_scanner import RepositoryScanner
from app.analyzers.dependency_graph import DependencyGraphBuilder
from app.models.analysis_models import (
    ClassInfo,
    FileAnalysis,
    FunctionInfo,
    RepositoryAnalysis,
)
from app.models.complexity_models import (
    ComplexityRating,
    ComplexityResult,
    ComplexitySummary,
    FunctionComplexity,
)

logger = logging.getLogger(__name__)

# Rating thresholds
_RATING_MODERATE = 6
_RATING_HIGH = 11
_RATING_VERY_HIGH = 21

# Top-N for most complex
_TOP_N = 20


def _rate_complexity(cc: int) -> ComplexityRating:
    """Map cyclomatic complexity to a rating."""
    if cc < _RATING_MODERATE:
        return ComplexityRating.LOW
    if cc < _RATING_HIGH:
        return ComplexityRating.MODERATE
    if cc < _RATING_VERY_HIGH:
        return ComplexityRating.HIGH
    return ComplexityRating.VERY_HIGH


class _ComplexityVisitor(ast.NodeVisitor):
    """AST visitor that calculates complexity metrics for a function body."""

    def __init__(self) -> None:
        self.complexity: int = 1  # base complexity
        self.branch_count: int = 0
        self.loop_count: int = 0
        self.call_count: int = 0
        self.max_nesting: int = 0
        self._current_depth: int = 0

    def _enter_nesting(self) -> None:
        self._current_depth += 1
        if self._current_depth > self.max_nesting:
            self.max_nesting = self._current_depth

    def _exit_nesting(self) -> None:
        self._current_depth -= 1

    # Decision points
    def visit_If(self, node: ast.If) -> None:
        self.complexity += 1
        self.branch_count += 1
        self._enter_nesting()
        self.generic_visit(node)
        self._exit_nesting()

    def visit_For(self, node: ast.For) -> None:
        self.complexity += 1
        self.loop_count += 1
        self._enter_nesting()
        self.generic_visit(node)
        self._exit_nesting()

    def visit_While(self, node: ast.While) -> None:
        self.complexity += 1
        self.loop_count += 1
        self._enter_nesting()
        self.generic_visit(node)
        self._exit_nesting()

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.complexity += 1
        self.branch_count += 1
        self._enter_nesting()
        self.generic_visit(node)
        self._exit_nesting()

    def visit_With(self, node: ast.With) -> None:
        self.complexity += 1
        self._enter_nesting()
        self.generic_visit(node)
        self._exit_nesting()

    def visit_Assert(self, node: ast.Assert) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        # Each 'and'/'or' adds a decision path
        self.complexity += len(node.values) - 1
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        # Ternary expression: x if cond else y
        self.complexity += 1
        self.branch_count += 1
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        # Each if-clause in a comprehension
        self.complexity += len(node.ifs)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        self.call_count += 1
        self.generic_visit(node)


def _module_name_from_path(file_path: str) -> str:
    """Derive module name from file path (matches dependency_graph.py convention)."""
    from pathlib import PurePosixPath
    p = PurePosixPath(file_path)
    if p.stem == '__init__':
        parts = list(p.parent.parts)
        return '.'.join(parts) if parts else '__init__'
    else:
        parts = list(p.parent.parts) + [p.stem]
        return '.'.join(parts)


class ComplexityAnalyzer:
    """Analyzes code complexity using Python AST.

    Calculates per-function metrics including cyclomatic complexity,
    lines of code, branches, loops, calls, parameters, and nesting depth.

    All analysis is static — no code is executed.
    """

    def analyze_repository(
        self,
        repo_path: Path,
        repo_analysis: RepositoryAnalysis | None = None,
        graph_builder: DependencyGraphBuilder | None = None,
    ) -> ComplexityResult:
        """Analyze complexity for all functions in a repository.

        Args:
            repo_path: Path to the repository.
            repo_analysis: Pre-computed repository analysis (optional, will scan if None).
            graph_builder: Pre-built dependency graph (optional, for graph metrics).

        Returns:
            ComplexityResult with per-function metrics and summary.
        """
        if repo_analysis is None:
            scanner = RepositoryScanner()
            repo_analysis = scanner.scan(repo_path)

        functions: list[FunctionComplexity] = []

        for file_analysis in repo_analysis.files:
            if file_analysis.has_syntax_error:
                continue
            file_functions = self._analyze_file(file_analysis)
            functions.extend(file_functions)

        # Enrich with graph metrics if available
        if graph_builder is not None:
            self._enrich_with_graph_metrics(functions, graph_builder)

        # Build summary
        summary = self._build_summary(functions)

        # Top-N most complex
        most_complex = sorted(
            functions,
            key=lambda f: (f.cyclomatic_complexity, f.lines_of_code),
            reverse=True,
        )[:_TOP_N]

        return ComplexityResult(
            repository_path=str(repo_path),
            functions=functions,
            summary=summary,
            most_complex=most_complex,
        )

    def _analyze_file(self, file_analysis: FileAnalysis) -> list[FunctionComplexity]:
        """Analyze all functions/methods in a single file."""
        results: list[FunctionComplexity] = []
        module_name = _module_name_from_path(file_analysis.file_path)

        # Re-parse the source to walk function bodies
        source_path = Path(file_analysis.absolute_path)
        try:
            source = source_path.read_text(encoding='utf-8')
            tree = ast.parse(source, filename=str(source_path))
        except (OSError, SyntaxError):
            return results

        # Top-level functions
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fc = self._analyze_function_node(
                    node, module_name, file_analysis.file_path,
                    is_method=False, class_name=None,
                )
                results.append(fc)

            elif isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        fc = self._analyze_function_node(
                            item, module_name, file_analysis.file_path,
                            is_method=True, class_name=node.name,
                        )
                        results.append(fc)

        return results

    def _analyze_function_node(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        module_name: str,
        file_path: str,
        is_method: bool,
        class_name: str | None,
    ) -> FunctionComplexity:
        """Analyze a single function/method AST node."""
        # Build component ID matching dependency graph convention
        if is_method and class_name:
            component_id = f'method:{module_name}.{class_name}.{node.name}'
            qualified_name = f'{class_name}.{node.name}'
        else:
            component_id = f'function:{module_name}.{node.name}'
            qualified_name = node.name

        # Calculate LOC
        start_line = node.lineno
        end_line = getattr(node, 'end_lineno', start_line)
        loc = max(1, (end_line or start_line) - start_line + 1)

        # Count parameters
        args = node.args
        param_count = (
            len(args.args)
            + len(args.kwonlyargs)
            + (1 if args.vararg else 0)
            + (1 if args.kwarg else 0)
        )
        # Exclude 'self' and 'cls' from parameter count for methods
        if is_method and args.args:
            first_arg = args.args[0].arg
            if first_arg in ('self', 'cls'):
                param_count -= 1

        # Visit function body for complexity metrics
        visitor = _ComplexityVisitor()
        for child in node.body:
            visitor.visit(child)

        cc = visitor.complexity
        rating = _rate_complexity(cc)

        return FunctionComplexity(
            component_id=component_id,
            name=node.name,
            qualified_name=qualified_name,
            file_path=file_path,
            line_number=start_line,
            end_line=end_line,
            cyclomatic_complexity=cc,
            lines_of_code=loc,
            branch_count=visitor.branch_count,
            loop_count=visitor.loop_count,
            call_count=visitor.call_count,
            parameter_count=param_count,
            max_nesting_depth=visitor.max_nesting,
            rating=rating,
            is_method=is_method,
        )

    def _enrich_with_graph_metrics(
        self,
        functions: list[FunctionComplexity],
        graph_builder: DependencyGraphBuilder,
    ) -> None:
        """Add dependency/dependent counts from the graph."""
        graph = graph_builder.graph
        for fc in functions:
            if fc.component_id in graph:
                fc.dependency_count = graph.out_degree(fc.component_id)
                fc.dependent_count = graph.in_degree(fc.component_id)

    def _build_summary(self, functions: list[FunctionComplexity]) -> ComplexitySummary:
        """Build aggregate complexity statistics."""
        if not functions:
            return ComplexitySummary()

        complexities = [f.cyclomatic_complexity for f in functions]

        return ComplexitySummary(
            total_functions=len(functions),
            average_complexity=round(statistics.mean(complexities), 2),
            median_complexity=round(statistics.median(complexities), 2),
            max_complexity=max(complexities),
            low_count=sum(1 for f in functions if f.rating == ComplexityRating.LOW),
            moderate_count=sum(1 for f in functions if f.rating == ComplexityRating.MODERATE),
            high_count=sum(1 for f in functions if f.rating == ComplexityRating.HIGH),
            very_high_count=sum(1 for f in functions if f.rating == ComplexityRating.VERY_HIGH),
            total_lines_of_code=sum(f.lines_of_code for f in functions),
        )
