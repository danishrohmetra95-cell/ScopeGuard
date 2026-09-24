"""Function-level change detection using AST comparison.

Compares Python source files between two versions (parent commit vs
target commit) to identify which functions, classes, and methods
were added, removed, or modified.

Strategy:
    1. Parse both versions using ASTAnalyzer.analyze_source()
    2. Compare components by name
    3. For same-named components, compare source text between
       [line_number : end_line] to detect modifications

Limitations:
    - Compares source text, not semantic meaning
    - Whitespace-only or comment-only changes are reported as modifications
    - Cannot detect function renames (reported as remove + add)
    - Cannot track moved functions across files
"""

import logging
import ast

import git

from app.analyzers.ast_analyzer import ASTAnalyzer
from app.analyzers.dependency_graph import _module_name_from_path
from app.models.analysis_models import ClassInfo, FunctionInfo
from app.models.change_models import (
    ChangeType,
    ComponentChange,
    ComponentChangeType,
    FileChange,
)
from app.models.graph_models import ComponentType
from app.services.git_service import GitService

logger = logging.getLogger(__name__)


class ChangeDetector:
    """Detects function-level changes between two versions of Python files."""

    def __init__(self) -> None:
        self._analyzer = ASTAnalyzer()
        self._git = GitService()

    def detect_changes(
        self,
        repo: git.Repo,
        commit_hash: str,
        file_changes: list[FileChange],
        base_hash: str | None = None,
    ) -> list[ComponentChange]:
        """Detect component-level changes for all changed Python files.

        Args:
            repo: Open Git repository.
            commit_hash: The commit to analyze.
            file_changes: File-level changes from GitService.
            base_hash: Optional base commit for range diffing (PR analysis).

        Returns:
            List of ComponentChange for each affected component.
        """
        commit = repo.commit(commit_hash)
        parent_hash = base_hash if base_hash else (commit.parents[0].hexsha if commit.parents else None)
        all_changes: list[ComponentChange] = []

        for fc in file_changes:
            if not fc.path.endswith('.py'):
                continue

            if fc.change_type == ChangeType.ADDED:
                all_changes.extend(
                    self._added_file(repo, commit_hash, fc),
                )
            elif fc.change_type == ChangeType.DELETED:
                all_changes.extend(
                    self._deleted_file(repo, parent_hash, fc),
                )
            elif fc.change_type == ChangeType.MODIFIED:
                all_changes.extend(
                    self._modified_file(repo, commit_hash, parent_hash, fc),
                )
            elif fc.change_type == ChangeType.RENAMED:
                all_changes.extend(
                    self._modified_file(
                        repo, commit_hash, parent_hash, fc,
                        old_path=fc.old_path,
                    ),
                )

        return all_changes

    # ------------------------------------------------------------------
    # Added file
    # ------------------------------------------------------------------

    def _added_file(
        self, repo: git.Repo, commit_hash: str, fc: FileChange,
    ) -> list[ComponentChange]:
        """All components in an added file are ADDED."""
        source = self._git.get_file_at_commit(repo, commit_hash, fc.path)
        if not source:
            return []

        analysis = self._analyzer.analyze_source(source, fc.path)
        if analysis.has_syntax_error:
            return []

        module_name = _module_name_from_path(fc.path)
        changes: list[ComponentChange] = []

        for func in analysis.functions:
            changes.append(ComponentChange(
                component_id=f'function:{module_name}.{func.name}',
                component_type=ComponentType.FUNCTION,
                change_type=ComponentChangeType.ADDED,
                file_path=fc.path,
                name=func.name,
                new_line_range=(
                    [func.line_number, func.end_line]
                    if func.end_line else None
                ),
            ))

        for cls in analysis.classes:
            changes.append(ComponentChange(
                component_id=f'class:{module_name}.{cls.name}',
                component_type=ComponentType.CLASS,
                change_type=ComponentChangeType.ADDED,
                file_path=fc.path,
                name=cls.name,
                new_line_range=(
                    [cls.line_number, cls.end_line]
                    if cls.end_line else None
                ),
            ))
            for method in cls.methods:
                changes.append(ComponentChange(
                    component_id=f'method:{module_name}.{cls.name}.{method.name}',
                    component_type=ComponentType.METHOD,
                    change_type=ComponentChangeType.ADDED,
                    file_path=fc.path,
                    name=method.name,
                    new_line_range=(
                        [method.line_number, method.end_line]
                        if method.end_line else None
                    ),
                ))

        return changes

    # ------------------------------------------------------------------
    # Deleted file
    # ------------------------------------------------------------------

    def _deleted_file(
        self, repo: git.Repo, parent_hash: str | None, fc: FileChange,
    ) -> list[ComponentChange]:
        """All components in a deleted file are REMOVED."""
        if parent_hash is None:
            return []

        source = self._git.get_file_at_commit(repo, parent_hash, fc.path)
        if not source:
            return []

        analysis = self._analyzer.analyze_source(source, fc.path)
        if analysis.has_syntax_error:
            return []

        module_name = _module_name_from_path(fc.path)
        changes: list[ComponentChange] = []

        for func in analysis.functions:
            changes.append(ComponentChange(
                component_id=f'function:{module_name}.{func.name}',
                component_type=ComponentType.FUNCTION,
                change_type=ComponentChangeType.REMOVED,
                file_path=fc.path,
                name=func.name,
                old_line_range=(
                    [func.line_number, func.end_line]
                    if func.end_line else None
                ),
            ))

        for cls in analysis.classes:
            changes.append(ComponentChange(
                component_id=f'class:{module_name}.{cls.name}',
                component_type=ComponentType.CLASS,
                change_type=ComponentChangeType.REMOVED,
                file_path=fc.path,
                name=cls.name,
                old_line_range=(
                    [cls.line_number, cls.end_line]
                    if cls.end_line else None
                ),
            ))
            for method in cls.methods:
                changes.append(ComponentChange(
                    component_id=f'method:{module_name}.{cls.name}.{method.name}',
                    component_type=ComponentType.METHOD,
                    change_type=ComponentChangeType.REMOVED,
                    file_path=fc.path,
                    name=method.name,
                    old_line_range=(
                        [method.line_number, method.end_line]
                        if method.end_line else None
                    ),
                ))

        return changes

    # ------------------------------------------------------------------
    # Modified file
    # ------------------------------------------------------------------

    def _modified_file(
        self,
        repo: git.Repo,
        commit_hash: str,
        parent_hash: str | None,
        fc: FileChange,
        old_path: str | None = None,
    ) -> list[ComponentChange]:
        """Compare old and new versions to find component changes."""
        if parent_hash is None:
            return self._added_file(repo, commit_hash, fc)

        source_old_path = old_path or fc.path
        new_source = self._git.get_file_at_commit(repo, commit_hash, fc.path)
        old_source = self._git.get_file_at_commit(repo, parent_hash, source_old_path)

        if new_source is None or old_source is None:
            return []

        new_analysis = self._analyzer.analyze_source(new_source, fc.path)
        old_analysis = self._analyzer.analyze_source(old_source, source_old_path)

        if new_analysis.has_syntax_error or old_analysis.has_syntax_error:
            module_name = _module_name_from_path(fc.path)
            return [ComponentChange(
                component_id=f'module:{module_name}',
                component_type=ComponentType.MODULE,
                change_type=ComponentChangeType.MODIFIED,
                file_path=fc.path,
                name=module_name,
            )]

        module_name = _module_name_from_path(fc.path)
        old_lines = old_source.splitlines()
        new_lines = new_source.splitlines()
        changes: list[ComponentChange] = []

        # Compare top-level functions
        changes.extend(self._compare_functions(
            old_analysis.functions, new_analysis.functions,
            module_name, fc.path, old_lines, new_lines,
        ))

        # Compare classes and their methods
        changes.extend(self._compare_classes(
            old_analysis.classes, new_analysis.classes,
            module_name, fc.path, old_lines, new_lines,
        ))

        return changes

    # ------------------------------------------------------------------
    # Comparison helpers
    # ------------------------------------------------------------------

    def _compare_functions(
        self,
        old_funcs: list[FunctionInfo],
        new_funcs: list[FunctionInfo],
        module_name: str,
        file_path: str,
        old_lines: list[str],
        new_lines: list[str],
        parent_class: str | None = None,
    ) -> list[ComponentChange]:
        """Compare function lists between old and new versions."""
        changes: list[ComponentChange] = []
        old_by_name = {f.name: f for f in old_funcs}
        new_by_name = {f.name: f for f in new_funcs}

        if parent_class:
            comp_type = ComponentType.METHOD
            id_prefix = f'method:{module_name}.{parent_class}'
        else:
            comp_type = ComponentType.FUNCTION
            id_prefix = f'function:{module_name}'

        # Added
        for name in new_by_name:
            if name not in old_by_name:
                func = new_by_name[name]
                changes.append(ComponentChange(
                    component_id=f'{id_prefix}.{name}',
                    component_type=comp_type,
                    change_type=ComponentChangeType.ADDED,
                    file_path=file_path,
                    name=name,
                    new_line_range=(
                        [func.line_number, func.end_line]
                        if func.end_line else None
                    ),
                ))

        # Removed
        for name in old_by_name:
            if name not in new_by_name:
                func = old_by_name[name]
                changes.append(ComponentChange(
                    component_id=f'{id_prefix}.{name}',
                    component_type=comp_type,
                    change_type=ComponentChangeType.REMOVED,
                    file_path=file_path,
                    name=name,
                    old_line_range=(
                        [func.line_number, func.end_line]
                        if func.end_line else None
                    ),
                ))

        # Modified (exist in both — compare source text)
        for name in old_by_name:
            if name in new_by_name:
                old_f = old_by_name[name]
                new_f = new_by_name[name]
                old_src = self._extract_source(old_f, old_lines)
                new_src = self._extract_source(new_f, new_lines)
                if old_src != new_src:
                    semantics = self._determine_semantics(old_src, new_src)
                    changes.append(ComponentChange(
                        component_id=f'{id_prefix}.{name}',
                        component_type=comp_type,
                        change_type=ComponentChangeType.MODIFIED,
                        file_path=file_path,
                        name=name,
                        old_line_range=(
                            [old_f.line_number, old_f.end_line]
                            if old_f.end_line else None
                        ),
                        new_line_range=(
                            [new_f.line_number, new_f.end_line]
                            if new_f.end_line else None
                        ),
                        change_semantics=semantics,
                    ))

        return changes

    def _compare_classes(
        self,
        old_classes: list[ClassInfo],
        new_classes: list[ClassInfo],
        module_name: str,
        file_path: str,
        old_lines: list[str],
        new_lines: list[str],
    ) -> list[ComponentChange]:
        """Compare class lists between old and new versions."""
        changes: list[ComponentChange] = []
        old_by_name = {c.name: c for c in old_classes}
        new_by_name = {c.name: c for c in new_classes}

        # Added classes
        for name in new_by_name:
            if name not in old_by_name:
                cls = new_by_name[name]
                changes.append(ComponentChange(
                    component_id=f'class:{module_name}.{name}',
                    component_type=ComponentType.CLASS,
                    change_type=ComponentChangeType.ADDED,
                    file_path=file_path,
                    name=name,
                    new_line_range=(
                        [cls.line_number, cls.end_line]
                        if cls.end_line else None
                    ),
                ))
                for method in cls.methods:
                    changes.append(ComponentChange(
                        component_id=f'method:{module_name}.{name}.{method.name}',
                        component_type=ComponentType.METHOD,
                        change_type=ComponentChangeType.ADDED,
                        file_path=file_path,
                        name=method.name,
                        new_line_range=(
                            [method.line_number, method.end_line]
                            if method.end_line else None
                        ),
                    ))

        # Removed classes
        for name in old_by_name:
            if name not in new_by_name:
                cls = old_by_name[name]
                changes.append(ComponentChange(
                    component_id=f'class:{module_name}.{name}',
                    component_type=ComponentType.CLASS,
                    change_type=ComponentChangeType.REMOVED,
                    file_path=file_path,
                    name=name,
                    old_line_range=(
                        [cls.line_number, cls.end_line]
                        if cls.end_line else None
                    ),
                ))
                for method in cls.methods:
                    changes.append(ComponentChange(
                        component_id=f'method:{module_name}.{name}.{method.name}',
                        component_type=ComponentType.METHOD,
                        change_type=ComponentChangeType.REMOVED,
                        file_path=file_path,
                        name=method.name,
                        old_line_range=(
                            [method.line_number, method.end_line]
                            if method.end_line else None
                        ),
                    ))

        # Modified classes — compare methods individually
        for name in old_by_name:
            if name in new_by_name:
                old_cls = old_by_name[name]
                new_cls = new_by_name[name]
                changes.extend(self._compare_functions(
                    old_cls.methods, new_cls.methods,
                    module_name, file_path, old_lines, new_lines,
                    parent_class=name,
                ))

        return changes

    def _determine_semantics(self, old_src: str, new_src: str) -> str:
        """Determine change semantics by comparing ASTs."""
        try:
            # Need to wrap in a class/module context if it's just a method to parse properly,
            # but usually ast.parse works fine on just function defs.
            old_ast = ast.parse(old_src)
            new_ast = ast.parse(new_src)
        except SyntaxError:
            return 'code-modification'
        
        if ast.dump(old_ast) == ast.dump(new_ast):
            return 'whitespace-or-comments-only'
            
        def remove_docstrings(node):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
                if (node.body and isinstance(node.body[0], ast.Expr) and 
                    isinstance(node.body[0].value, ast.Constant) and 
                    isinstance(node.body[0].value.value, str)):
                    node.body = node.body[1:]
                    if not node.body:
                        node.body = [ast.Pass()]
            for child in ast.iter_child_nodes(node):
                remove_docstrings(child)
            return node
            
        old_no_doc = remove_docstrings(ast.parse(old_src))
        new_no_doc = remove_docstrings(ast.parse(new_src))
        
        if ast.dump(old_no_doc) == ast.dump(new_no_doc):
            return 'documentation-only'
            
        return 'code-modification'

    def _extract_source(
        self, func: FunctionInfo, lines: list[str],
    ) -> str:
        """Extract source text for a function from the file lines."""
        start = func.line_number - 1  # 0-indexed
        end = func.end_line if func.end_line else start + 1
        return '\n'.join(lines[start:end])
