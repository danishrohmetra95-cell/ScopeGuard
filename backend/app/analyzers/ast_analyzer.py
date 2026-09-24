"""AST-based Python source code analyzer.

Uses Python's built-in ast module to extract structural information
from Python source files. This is static analysis only and cannot
determine runtime behavior.
"""

import ast
import logging
from pathlib import Path

from app.analyzers.language_analyzer import LanguageAnalyzer
from app.models.analysis_models import (
    CallInfo,
    ClassInfo,
    DynamicDependencyInfo,
    FileAnalysis,
    FunctionInfo,
    ImportInfo,
    ParameterInfo,
    RouteInfo,
)

logger = logging.getLogger(__name__)

# Common HTTP method decorators for route detection
_HTTP_METHODS = frozenset({'get', 'post', 'put', 'delete', 'patch', 'head', 'options'})


class ASTAnalyzer(LanguageAnalyzer):
    """Parses Python source code into an Abstract Syntax Tree (AST).
    
    Extracts structural information such as imports, function definitions,
    class definitions, and function calls. Implements the LanguageAnalyzer protocol.

    This analyzer performs static analysis only. It cannot determine
    runtime behavior, dynamic imports, or dynamically generated code.
    Route detection is best-effort and may not catch all patterns.
    """

    def analyze_file(self, file_path: Path, relative_path: str) -> FileAnalysis:
        """Analyze a single Python file.
        
        Args:
            file_path: Absolute path to the Python file.
            relative_path: Path relative to repository root.
            
        Returns:
            FileAnalysis with extracted information.
        """
        result = FileAnalysis(
            file_path=relative_path,
            absolute_path=str(file_path),
        )
        
        try:
            source = file_path.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError) as e:
            logger.warning('Could not read file %s: %s', file_path, e)
            result.has_syntax_error = True
            result.syntax_error_message = f'Could not read file: {e}'
            return result
        
        lines = source.splitlines()
        result.line_count = len(lines)
        result.file_size_bytes = file_path.stat().st_size
        
        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError as e:
            logger.warning('Syntax error in %s: %s', file_path, e)
            result.has_syntax_error = True
            result.syntax_error_message = f'Syntax error: {e.msg} (line {e.lineno})'
            return result
        
        result.imports = self._extract_imports(tree)
        result.classes = self._extract_classes(tree)
        result.functions = self._extract_top_level_functions(tree)
        result.calls = self._extract_calls(tree)
        result.routes = self._extract_routes(tree)
        
        return result

    def analyze_source(
        self, source: str, file_path: str = '<string>',
    ) -> FileAnalysis:
        """Analyze Python source code from a string.

        Used by the change detector to parse file contents retrieved
        from Git commits without writing to disk.

        Args:
            source: Python source code as a string.
            file_path: Logical file path (for error messages and metadata).

        Returns:
            FileAnalysis with extracted information.
        """
        result = FileAnalysis(
            file_path=file_path,
            absolute_path=file_path,
        )

        lines = source.splitlines()
        result.line_count = len(lines)
        result.file_size_bytes = len(source.encode('utf-8'))

        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError as e:
            result.has_syntax_error = True
            result.syntax_error_message = f'Syntax error: {e.msg} (line {e.lineno})'
            return result

        result.imports = self._extract_imports(tree)
        
        dynamic_imports, unresolved_dyn = self._extract_dynamic_dependencies(tree)
        result.imports.extend(dynamic_imports)
        result.unresolved_dynamic_dependencies = unresolved_dyn
        
        result.classes = self._extract_classes(tree)
        result.functions = self._extract_top_level_functions(tree)
        result.calls = self._extract_calls(tree)
        result.routes = self._extract_routes(tree)

        return result

    def _extract_imports(self, tree: ast.Module) -> list[ImportInfo]:
        """Extract all import statements from the AST."""
        imports: list[ImportInfo] = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(ImportInfo(
                        module=alias.name,
                        name=None,
                        alias=alias.asname,
                        line_number=node.lineno,
                        statement=f'import {alias.name}' + (f' as {alias.asname}' if alias.asname else ''),
                    ))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    imports.append(ImportInfo(
                        module=module,
                        name=alias.name,
                        alias=alias.asname,
                        line_number=node.lineno,
                        statement=f'from {module} import {alias.name}' + (f' as {alias.asname}' if alias.asname else ''),
                    ))
        
        return imports

    def _extract_dynamic_dependencies(self, tree: ast.Module) -> tuple[list[ImportInfo], list[DynamicDependencyInfo]]:
        """Detect dynamic imports and unresolved behaviors (eval/exec)."""
        dynamic_imports: list[ImportInfo] = []
        unresolved: list[DynamicDependencyInfo] = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = ''
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                
                if func_name in ('__import__', 'import_module'):
                    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                        module_name = node.args[0].value
                        dynamic_imports.append(ImportInfo(
                            module=module_name,
                            name=None,
                            alias=None,
                            line_number=node.lineno,
                            statement=f"{func_name}('{module_name}')",
                            is_dynamic=True
                        ))
                    else:
                        try:
                            snippet = ast.unparse(node)
                        except Exception:
                            snippet = f"{func_name}(...)"
                        unresolved.append(DynamicDependencyInfo(
                            pattern=f"dynamic_{func_name}",
                            line_number=node.lineno,
                            source_snippet=snippet
                        ))
                elif func_name in ('eval', 'exec'):
                    try:
                        snippet = ast.unparse(node)
                    except Exception:
                        snippet = f"{func_name}(...)"
                    unresolved.append(DynamicDependencyInfo(
                        pattern=func_name,
                        line_number=node.lineno,
                        source_snippet=snippet
                    ))
        
        return dynamic_imports, unresolved

    def _extract_function_info(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        parent_class: str | None = None,
    ) -> FunctionInfo:
        """Extract information from a function/method definition node."""
        name = node.name
        qualified_name = f'{parent_class}.{name}' if parent_class else name
        
        parameters = self._extract_parameters(node.args)
        decorators = self._extract_decorator_names(node.decorator_list)
        
        docstring: str | None = None
        if (node.body 
                and isinstance(node.body[0], ast.Expr) 
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)):
            docstring = node.body[0].value.value
        
        return FunctionInfo(
            name=name,
            qualified_name=qualified_name,
            line_number=node.lineno,
            end_line=getattr(node, 'end_lineno', None),
            parameters=parameters,
            decorators=decorators,
            is_method=parent_class is not None,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            docstring=docstring,
        )

    def _extract_parameters(self, args: ast.arguments) -> list[ParameterInfo]:
        """Extract parameter information from function arguments."""
        params: list[ParameterInfo] = []
        
        # Calculate defaults offset: defaults apply to the LAST len(defaults) args
        num_args = len(args.args)
        num_defaults = len(args.defaults)
        default_offset = num_args - num_defaults
        
        for i, arg in enumerate(args.args):
            annotation = None
            if arg.annotation:
                annotation = ast.unparse(arg.annotation)
            
            default = None
            default_index = i - default_offset
            if default_index >= 0 and default_index < len(args.defaults):
                default = ast.unparse(args.defaults[default_index])
            
            params.append(ParameterInfo(
                name=arg.arg,
                annotation=annotation,
                default=default,
            ))
        
        # *args
        if args.vararg:
            annotation = ast.unparse(args.vararg.annotation) if args.vararg.annotation else None
            params.append(ParameterInfo(name=f'*{args.vararg.arg}', annotation=annotation))
        
        # keyword-only args
        for i, arg in enumerate(args.kwonlyargs):
            annotation = ast.unparse(arg.annotation) if arg.annotation else None
            default = None
            if i < len(args.kw_defaults) and args.kw_defaults[i] is not None:
                default = ast.unparse(args.kw_defaults[i])
            params.append(ParameterInfo(name=arg.arg, annotation=annotation, default=default))
        
        # **kwargs
        if args.kwarg:
            annotation = ast.unparse(args.kwarg.annotation) if args.kwarg.annotation else None
            params.append(ParameterInfo(name=f'**{args.kwarg.arg}', annotation=annotation))
        
        return params

    def _extract_decorator_names(self, decorator_list: list[ast.expr]) -> list[str]:
        """Extract decorator names from a decorator list."""
        decorators: list[str] = []
        for dec in decorator_list:
            try:
                decorators.append(ast.unparse(dec))
            except Exception:
                decorators.append('<unknown decorator>')
        return decorators

    def _extract_classes(self, tree: ast.Module) -> list[ClassInfo]:
        """Extract all top-level class definitions."""
        classes: list[ClassInfo] = []
        
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                classes.append(self._extract_class_info(node))
        
        return classes

    def _extract_class_info(self, node: ast.ClassDef) -> ClassInfo:
        """Extract information from a class definition node."""
        base_classes: list[str] = []
        for base in node.bases:
            try:
                base_classes.append(ast.unparse(base))
            except Exception:
                base_classes.append('<unknown>')
        
        methods: list[FunctionInfo] = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(self._extract_function_info(item, parent_class=node.name))
        
        decorators = self._extract_decorator_names(node.decorator_list)
        
        docstring: str | None = None
        if (node.body 
                and isinstance(node.body[0], ast.Expr) 
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)):
            docstring = node.body[0].value.value
        
        return ClassInfo(
            name=node.name,
            line_number=node.lineno,
            end_line=getattr(node, 'end_lineno', None),
            base_classes=base_classes,
            methods=methods,
            decorators=decorators,
            docstring=docstring,
        )

    def _extract_top_level_functions(self, tree: ast.Module) -> list[FunctionInfo]:
        """Extract top-level function definitions (not class methods)."""
        functions: list[FunctionInfo] = []
        
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(self._extract_function_info(node))
        
        return functions

    def _extract_calls(self, tree: ast.Module) -> list[CallInfo]:
        """Extract function/method calls from the AST.
        
        Only extracts statically identifiable call names.
        Dynamic calls and complex expressions are skipped.
        """
        calls: list[CallInfo] = []
        
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            
            name: str | None = None
            is_method_call = False
            
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                is_method_call = True
                # Try to build the dotted name
                parts: list[str] = [node.func.attr]
                current = node.func.value
                while isinstance(current, ast.Attribute):
                    parts.append(current.attr)
                    current = current.value
                if isinstance(current, ast.Name):
                    parts.append(current.id)
                parts.reverse()
                name = '.'.join(parts)
            
            if name:
                calls.append(CallInfo(
                    name=name,
                    line_number=node.lineno,
                    is_method_call=is_method_call,
                ))
        
        return calls

    def _extract_routes(self, tree: ast.Module) -> list[RouteInfo]:
        """Best-effort detection of API route definitions.
        
        Detects common decorator patterns like:
        - @app.get('/path')
        - @app.post('/path')
        - @router.get('/path')
        - @blueprint.route('/path', methods=['GET'])
        
        This is heuristic-based and may not detect all route patterns.
        It cannot determine routes defined at runtime.
        """
        routes: list[RouteInfo] = []
        
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            
            for decorator in node.decorator_list:
                route_info = self._check_route_decorator(decorator, node.name, node.lineno)
                if route_info:
                    routes.append(route_info)
        
        return routes

    def _check_route_decorator(
        self,
        decorator: ast.expr,
        func_name: str,
        line_number: int,
    ) -> RouteInfo | None:
        """Check if a decorator represents an API route definition."""
        # Pattern: @app.get('/path') or @router.post('/path')
        if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
            method_name = decorator.func.attr.lower()
            
            if method_name in _HTTP_METHODS:
                path = self._extract_route_path(decorator)
                return RouteInfo(
                    path=path,
                    http_method=method_name.upper(),
                    function_name=func_name,
                    line_number=line_number,
                    framework_hint='fastapi/flask-like',
                )
            
            # Pattern: @app.route('/path') or @blueprint.route('/path')
            if method_name == 'route':
                path = self._extract_route_path(decorator)
                http_method = self._extract_methods_kwarg(decorator)
                return RouteInfo(
                    path=path,
                    http_method=http_method,
                    function_name=func_name,
                    line_number=line_number,
                    framework_hint='flask-like',
                )
        
        # Pattern: @app.api_route('/path')
        if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
            if decorator.func.attr == 'api_route':
                path = self._extract_route_path(decorator)
                return RouteInfo(
                    path=path,
                    http_method='MULTIPLE',
                    function_name=func_name,
                    line_number=line_number,
                    framework_hint='fastapi',
                )
        
        return None

    def _extract_route_path(self, decorator: ast.Call) -> str | None:
        """Extract the route path from a decorator call's first argument."""
        if decorator.args:
            first_arg = decorator.args[0]
            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                return first_arg.value
        return None

    def _extract_methods_kwarg(self, decorator: ast.Call) -> str:
        """Extract HTTP method from a methods keyword argument."""
        for kw in decorator.keywords:
            if kw.arg == 'methods' and isinstance(kw.value, ast.List):
                methods = []
                for elt in kw.value.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        methods.append(elt.value.upper())
                if methods:
                    return ','.join(methods)
        return 'GET'
