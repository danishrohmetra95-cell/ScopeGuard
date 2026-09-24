"""LanguageAnalyzer protocol for supporting multiple programming languages.

This module defines the interface that all language-specific AST analyzers
must implement to participate in the ScopeGuard analysis pipeline.
"""

from pathlib import Path
from typing import Protocol, runtime_checkable

from app.models.analysis_models import FileAnalysis


@runtime_checkable
class LanguageAnalyzer(Protocol):
    """Protocol defining the interface for language-specific analyzers.
    
    Implementations of this protocol are responsible for parsing source code
    in a specific programming language and extracting structural information
    (imports, functions, classes, calls) into the common FileAnalysis model.
    """

    def analyze_file(self, file_path: Path, relative_path: str) -> FileAnalysis:
        """Analyze a source code file.

        Args:
            file_path: Absolute path to the file to analyze.
            relative_path: Logical path of the file relative to the repository root.

        Returns:
            FileAnalysis: Extracted structural information from the file.
        """
        ...

    def analyze_source(self, source: str, file_path: str = '<string>') -> FileAnalysis:
        """Analyze source code from a string.

        Used by the change detector to parse file contents retrieved
        from Git commits without writing to disk.

        Args:
            source: Source code as a string.
            file_path: Logical file path (for error messages and metadata).

        Returns:
            FileAnalysis: Extracted structural information from the source.
        """
        ...
