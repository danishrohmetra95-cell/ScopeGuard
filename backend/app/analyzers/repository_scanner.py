"""Repository scanner for discovering and analyzing Python source files.

Scans a local repository directory, discovers Python files while respecting
exclusion rules, and orchestrates AST analysis of each file.
"""

import logging
from pathlib import Path

from app.analyzers.ast_analyzer import ASTAnalyzer
from app.core.config import get_settings
from app.models.analysis_models import (
    AnalysisWarning,
    FileAnalysis,
    RepositoryAnalysis,
    RepositorySummary,
)

logger = logging.getLogger(__name__)


class RepositoryTooLargeError(Exception):
    """Raised when repository exceeds configuration limits."""
    pass



class RepositoryScanner:
    """Scans a local repository to discover and analyze Python files.
    
    Recursively walks the directory tree, skipping excluded directories,
    and uses ASTAnalyzer to extract structural information from each
    Python source file found.
    """

    def __init__(self, excluded_dirs: set[str] | None = None) -> None:
        """Initialize the scanner.
        
        Args:
            excluded_dirs: Set of directory names to skip during scanning.
                          Uses defaults from settings if not provided.
        """
        settings = get_settings()
        self._excluded_dirs = excluded_dirs if excluded_dirs is not None else settings.excluded_dirs
        self._analyzer = ASTAnalyzer()
        self._max_file_size = settings.max_file_size_bytes
        self._max_file_count = settings.max_file_count

    def scan(self, repository_path: str | Path) -> RepositoryAnalysis:
        """Scan a repository and analyze all Python files.
        
        Args:
            repository_path: Path to the repository root directory.
            
        Returns:
            RepositoryAnalysis containing analysis of all discovered files.
            
        Raises:
            FileNotFoundError: If the repository path does not exist.
            NotADirectoryError: If the path exists but is not a directory.
            PermissionError: If the directory cannot be read.
        """
        repo_path = Path(repository_path).resolve()
        
        # Validate the repository path
        if not repo_path.exists():
            raise FileNotFoundError(f'Repository path does not exist: {repo_path}')
        if not repo_path.is_dir():
            raise NotADirectoryError(f'Repository path is not a directory: {repo_path}')
        
        # Check readability
        try:
            list(repo_path.iterdir())
        except PermissionError as e:
            raise PermissionError(f'Cannot read repository directory: {repo_path}') from e
        
        logger.info('Scanning repository: %s', repo_path)
        
        # Discover Python files
        try:
            python_files = self.discover_python_files(repo_path)
        except RepositoryTooLargeError as e:
            raise e
        logger.info('Discovered %d Python files', len(python_files))
        
        # Analyze each file
        file_analyses: list[FileAnalysis] = []
        warnings: list[AnalysisWarning] = []
        
        for py_file in sorted(python_files):
            relative_path = str(py_file.relative_to(repo_path)).replace('\\', '/')
            
            # Check file size
            try:
                file_size = py_file.stat().st_size
                if file_size > self._max_file_size:
                    warnings.append(AnalysisWarning(
                        file_path=relative_path,
                        message=f'File exceeds maximum size ({file_size} bytes > {self._max_file_size} bytes)',
                        warning_type='file_too_large',
                    ))
                    continue
            except OSError as e:
                warnings.append(AnalysisWarning(
                    file_path=relative_path,
                    message=f'Could not stat file: {e}',
                    warning_type='os_error',
                ))
                continue
            
            try:
                analysis = self._analyzer.analyze_file(py_file, relative_path)
                file_analyses.append(analysis)
                
                if analysis.has_syntax_error:
                    warnings.append(AnalysisWarning(
                        file_path=relative_path,
                        message=analysis.syntax_error_message or 'Unknown syntax error',
                        warning_type='syntax_error',
                    ))
            except Exception as e:
                logger.error('Unexpected error analyzing %s: %s', py_file, e)
                warnings.append(AnalysisWarning(
                    file_path=relative_path,
                    message=f'Unexpected error: {e}',
                    warning_type='unexpected_error',
                ))
        
        # Build summary
        summary = self._build_summary(file_analyses)
        
        result = RepositoryAnalysis(
            repository_path=str(repo_path),
            files=file_analyses,
            summary=summary,
            warnings=warnings,
            excluded_directories=sorted(self._excluded_dirs),
        )
        
        logger.info(
            'Analysis complete: %d files, %d functions, %d classes',
            summary.total_files,
            summary.total_functions,
            summary.total_classes,
        )
        
        return result

    def discover_python_files(self, root: Path) -> list[Path]:
        """Recursively discover Python files, respecting exclusion rules.
        
        Args:
            root: Root directory to start scanning from.
            
        Returns:
            List of Path objects for discovered .py files.
        """
        python_files: list[Path] = []
        self._walk_directory(root, python_files)
        return python_files

    def _walk_directory(self, directory: Path, results: list[Path]) -> None:
        """Recursively walk a directory collecting Python files."""
        try:
            entries = sorted(directory.iterdir())
        except PermissionError:
            logger.warning('Permission denied: %s', directory)
            return
        except OSError as e:
            logger.warning('Error reading directory %s: %s', directory, e)
            return
        
        for entry in entries:
            if entry.is_dir():
                if entry.name not in self._excluded_dirs:
                    self._walk_directory(entry, results)
            elif entry.is_file() and entry.suffix == '.py':
                if len(results) >= self._max_file_count:
                    raise RepositoryTooLargeError(f"Repository exceeds maximum allowed file count ({self._max_file_count})")
                results.append(entry)

    def _build_summary(self, file_analyses: list[FileAnalysis]) -> RepositorySummary:
        """Build summary statistics from file analyses."""
        total_functions = 0
        total_classes = 0
        total_imports = 0
        total_calls = 0
        total_routes = 0
        total_lines = 0
        files_with_errors = 0
        
        for fa in file_analyses:
            total_lines += fa.line_count
            total_imports += len(fa.imports)
            total_calls += len(fa.calls)
            total_routes += len(fa.routes)
            
            # Count top-level functions + class methods
            total_functions += len(fa.functions)
            for cls in fa.classes:
                total_functions += len(cls.methods)
            
            total_classes += len(fa.classes)
            
            if fa.has_syntax_error:
                files_with_errors += 1
        
        return RepositorySummary(
            total_files=len(file_analyses),
            total_lines=total_lines,
            total_functions=total_functions,
            total_classes=total_classes,
            total_imports=total_imports,
            total_calls=total_calls,
            total_routes=total_routes,
            files_with_errors=files_with_errors,
        )
