"""Static test discovery for Python repositories.

Discovers test files and test functions/methods using AST analysis.
Follows pytest and unittest naming conventions:

    Files:  test_*.py, *_test.py
    Funcs:  test_*
    Classes: Test*
    Methods: test_*

SAFETY: This module NEVER imports or executes code from the analyzed
repository. All analysis is purely static via the ast module.
"""

import logging
from pathlib import Path

from app.analyzers.ast_analyzer import ASTAnalyzer
from app.analyzers.dependency_graph import _module_name_from_path
from app.models.analysis_models import FileAnalysis
from app.models.test_models import TestCase, TestMapping

logger = logging.getLogger(__name__)

# Patterns for test file detection
_TEST_FILE_PREFIXES = ('test_',)
_TEST_FILE_SUFFIXES = ('_test.py',)
_TEST_FUNC_PREFIX = 'test_'
_TEST_CLASS_PREFIX = 'Test'


class TestAnalyzer:
    """Discovers tests and builds test-to-component mappings.

    All discovery is static — no code from the analyzed repo is executed.
    """

    def __init__(self) -> None:
        self._analyzer = ASTAnalyzer()

    def discover_tests(self, repo_path: Path) -> list[TestCase]:
        """Discover all test cases in a repository.

        Args:
            repo_path: Root of the repository to scan.

        Returns:
            List of TestCase for every detected test function/method.
        """
        test_files = self._find_test_files(repo_path)
        tests: list[TestCase] = []

        for tf in test_files:
            relative = str(tf.relative_to(repo_path)).replace('\\', '/')
            analysis = self._analyzer.analyze_file(tf, relative)
            if analysis.has_syntax_error:
                logger.warning('Skipping %s (syntax error)', relative)
                continue
            tests.extend(self._extract_tests(analysis, relative))

        logger.info('Discovered %d tests in %s', len(tests), repo_path)
        return tests

    def build_mappings(
        self,
        tests: list[TestCase],
        repo_path: Path,
        graph_node_ids: set[str] | None = None,
    ) -> list[TestMapping]:
        """Build mappings from tests to application components.

        For each test file, inspects imports and function calls to
        determine which application modules/functions the test references.

        Args:
            tests: Discovered test cases.
            repo_path: Repository root.
            graph_node_ids: Known component IDs from the dependency graph
                            (used to verify mappings against actual nodes).

        Returns:
            List of TestMapping, one per unique test file.
        """
        known_ids = graph_node_ids or set()

        # Group tests by file to avoid re-parsing
        files_seen: dict[str, FileAnalysis] = {}
        mappings_by_file: dict[str, TestMapping] = {}

        for test in tests:
            if test.test_file in files_seen:
                analysis = files_seen[test.test_file]
            else:
                abs_path = repo_path / test.test_file
                analysis = self._analyzer.analyze_file(abs_path, test.test_file)
                files_seen[test.test_file] = analysis

            if test.test_file not in mappings_by_file:
                ref_modules, ref_functions, ref_ids = (
                    self._extract_references(analysis, known_ids)
                )
                mappings_by_file[test.test_file] = TestMapping(
                    test_id=test.test_file,
                    referenced_modules=ref_modules,
                    referenced_functions=ref_functions,
                    referenced_component_ids=ref_ids,
                )

        # Build per-test mappings inheriting from file-level
        result: list[TestMapping] = []
        for test in tests:
            file_mapping = mappings_by_file.get(test.test_file)
            if file_mapping:
                result.append(TestMapping(
                    test_id=test.test_id,
                    referenced_modules=file_mapping.referenced_modules,
                    referenced_functions=file_mapping.referenced_functions,
                    referenced_component_ids=file_mapping.referenced_component_ids,
                ))

        return result

    # ------------------------------------------------------------------
    # Internal: file discovery
    # ------------------------------------------------------------------

    def _find_test_files(self, repo_path: Path) -> list[Path]:
        """Find all test files in the repository."""
        test_files: list[Path] = []
        excluded = {'.git', '__pycache__', 'venv', '.venv', 'node_modules',
                    '.tox', '.eggs', '.mypy_cache'}

        for py_file in repo_path.rglob('*.py'):
            if any(part in excluded for part in py_file.parts):
                continue
            name = py_file.name
            if (name.startswith(_TEST_FILE_PREFIXES)
                    or name.endswith(_TEST_FILE_SUFFIXES)):
                test_files.append(py_file)

        return sorted(test_files)

    # ------------------------------------------------------------------
    # Internal: extract tests from a file analysis
    # ------------------------------------------------------------------

    def _extract_tests(
        self, analysis: FileAnalysis, relative_path: str,
    ) -> list[TestCase]:
        """Extract test functions and test class methods."""
        module_name = _module_name_from_path(relative_path)
        tests: list[TestCase] = []

        # Top-level test functions
        for func in analysis.functions:
            if func.name.startswith(_TEST_FUNC_PREFIX):
                test_id = f'{relative_path}::{func.name}'
                tests.append(TestCase(
                    test_id=test_id,
                    test_file=relative_path,
                    test_name=func.name,
                    line_number=func.line_number,
                    module_name=module_name,
                ))

        # Test classes and their methods
        for cls in analysis.classes:
            if cls.name.startswith(_TEST_CLASS_PREFIX):
                for method in cls.methods:
                    if method.name.startswith(_TEST_FUNC_PREFIX):
                        test_id = f'{relative_path}::{cls.name}::{method.name}'
                        tests.append(TestCase(
                            test_id=test_id,
                            test_file=relative_path,
                            test_name=method.name,
                            class_name=cls.name,
                            line_number=method.line_number,
                            module_name=module_name,
                        ))

        return tests

    # ------------------------------------------------------------------
    # Internal: extract references to application components
    # ------------------------------------------------------------------

    def _extract_references(
        self,
        analysis: FileAnalysis,
        known_ids: set[str],
    ) -> tuple[list[str], list[str], list[str]]:
        """Extract module and function references from a test file.

        Returns:
            (referenced_modules, referenced_functions, referenced_component_ids)
        """
        ref_modules: list[str] = []
        ref_functions: list[str] = []
        ref_ids: list[str] = []

        # From imports
        for imp in analysis.imports:
            module = imp.module or ''
            # Skip standard library / test framework imports
            if module in ('pytest', 'unittest', 'os', 'sys', 'pathlib',
                          'typing', 'collections', 'json', 'datetime',
                          'logging', 'uuid', 'math', 're', 'textwrap',
                          'tempfile', 'shutil', 'io', 'abc', 'functools',
                          'dataclasses', 'enum', 'copy'):
                continue
            if module and module not in ref_modules:
                ref_modules.append(module)
                mod_id = f'module:{module}'
                if mod_id not in ref_ids:
                    ref_ids.append(mod_id)
            # Named imports (from module import name)
            if imp.name and module:
                func_id = f'function:{module}.{imp.name}'
                class_id = f'class:{module}.{imp.name}'
                if func_id in known_ids:
                    if func_id not in ref_ids:
                        ref_ids.append(func_id)
                    if imp.name not in ref_functions:
                        ref_functions.append(imp.name)
                elif class_id in known_ids:
                    if class_id not in ref_ids:
                        ref_ids.append(class_id)

        # From function calls
        for call in analysis.calls:
            call_name = call.name
            # Try matching against known graph IDs
            for mod in ref_modules:
                cid = f'function:{mod}.{call_name}'
                if cid in known_ids and cid not in ref_ids:
                    ref_ids.append(cid)
                    if call_name not in ref_functions:
                        ref_functions.append(call_name)

        return ref_modules, ref_functions, ref_ids
