"""Tests for the AST analyzer."""

import textwrap
from pathlib import Path

import pytest

from app.analyzers.ast_analyzer import ASTAnalyzer


@pytest.fixture
def analyzer():
    return ASTAnalyzer()


class TestFunctionExtraction:
    """Tests for function extraction."""

    def test_extracts_top_level_functions(self, analyzer: ASTAnalyzer, tmp_path: Path):
        source = textwrap.dedent('''
            def foo(x: int) -> str:
                return str(x)

            def bar(a, b=10):
                pass
        ''').lstrip()
        f = tmp_path / 'test.py'
        f.write_text(source)
        result = analyzer.analyze_file(f, 'test.py')

        assert len(result.functions) == 2
        assert result.functions[0].name == 'foo'
        assert result.functions[0].qualified_name == 'foo'
        assert result.functions[0].is_method is False
        assert result.functions[1].name == 'bar'

    def test_extracts_function_parameters(self, analyzer: ASTAnalyzer, tmp_path: Path):
        source = textwrap.dedent('''
            def func(a: int, b: str = "hello", *args, key: bool = True, **kwargs) -> None:
                pass
        ''').lstrip()
        f = tmp_path / 'test.py'
        f.write_text(source)
        result = analyzer.analyze_file(f, 'test.py')

        func = result.functions[0]
        param_names = [p.name for p in func.parameters]
        assert 'a' in param_names
        assert 'b' in param_names
        assert '*args' in param_names
        assert 'key' in param_names
        assert '**kwargs' in param_names

        # Check annotation
        a_param = next(p for p in func.parameters if p.name == 'a')
        assert a_param.annotation == 'int'

        # Check default
        b_param = next(p for p in func.parameters if p.name == 'b')
        assert b_param.default == "'hello'"

    def test_extracts_async_functions(self, analyzer: ASTAnalyzer, tmp_path: Path):
        source = textwrap.dedent('''
            async def async_handler(request):
                return "ok"
        ''').lstrip()
        f = tmp_path / 'test.py'
        f.write_text(source)
        result = analyzer.analyze_file(f, 'test.py')

        assert len(result.functions) == 1
        assert result.functions[0].is_async is True

    def test_extracts_function_docstrings(self, analyzer: ASTAnalyzer, tmp_path: Path):
        source = textwrap.dedent('''
            def documented():
                """This function has a docstring."""
                pass

            def undocumented():
                pass
        ''').lstrip()
        f = tmp_path / 'test.py'
        f.write_text(source)
        result = analyzer.analyze_file(f, 'test.py')

        assert result.functions[0].docstring == 'This function has a docstring.'
        assert result.functions[1].docstring is None


class TestClassExtraction:
    """Tests for class extraction."""

    def test_extracts_classes(self, analyzer: ASTAnalyzer, tmp_path: Path):
        source = textwrap.dedent('''
            class Base:
                pass

            class Child(Base):
                def method(self):
                    pass
        ''').lstrip()
        f = tmp_path / 'test.py'
        f.write_text(source)
        result = analyzer.analyze_file(f, 'test.py')

        assert len(result.classes) == 2
        assert result.classes[0].name == 'Base'
        assert result.classes[0].base_classes == []
        assert result.classes[1].name == 'Child'
        assert result.classes[1].base_classes == ['Base']

    def test_extracts_class_methods(self, analyzer: ASTAnalyzer, tmp_path: Path):
        source = textwrap.dedent('''
            class MyClass:
                def __init__(self):
                    pass

                def method(self, x: int) -> str:
                    return str(x)

                async def async_method(self):
                    pass
        ''').lstrip()
        f = tmp_path / 'test.py'
        f.write_text(source)
        result = analyzer.analyze_file(f, 'test.py')

        cls = result.classes[0]
        assert len(cls.methods) == 3
        assert cls.methods[0].name == '__init__'
        assert cls.methods[0].is_method is True
        assert cls.methods[0].qualified_name == 'MyClass.__init__'
        assert cls.methods[2].is_async is True

    def test_extracts_class_decorators(self, analyzer: ASTAnalyzer, tmp_path: Path):
        source = textwrap.dedent('''
            from dataclasses import dataclass

            @dataclass
            class Config:
                value: int = 0
        ''').lstrip()
        f = tmp_path / 'test.py'
        f.write_text(source)
        result = analyzer.analyze_file(f, 'test.py')

        assert len(result.classes) == 1
        assert 'dataclass' in result.classes[0].decorators

    def test_extracts_class_docstrings(self, analyzer: ASTAnalyzer, tmp_path: Path):
        source = textwrap.dedent('''
            class Documented:
                """This class has a docstring."""
                pass
        ''').lstrip()
        f = tmp_path / 'test.py'
        f.write_text(source)
        result = analyzer.analyze_file(f, 'test.py')

        assert result.classes[0].docstring == 'This class has a docstring.'


class TestImportExtraction:
    """Tests for import extraction."""

    def test_extracts_simple_imports(self, analyzer: ASTAnalyzer, tmp_path: Path):
        source = textwrap.dedent('''
            import os
            import sys
        ''').lstrip()
        f = tmp_path / 'test.py'
        f.write_text(source)
        result = analyzer.analyze_file(f, 'test.py')

        assert len(result.imports) == 2
        assert result.imports[0].module == 'os'
        assert result.imports[0].statement == 'import os'

    def test_extracts_from_imports(self, analyzer: ASTAnalyzer, tmp_path: Path):
        source = textwrap.dedent('''
            from os.path import join, exists
            from sys import argv
        ''').lstrip()
        f = tmp_path / 'test.py'
        f.write_text(source)
        result = analyzer.analyze_file(f, 'test.py')

        assert len(result.imports) == 3
        modules = [i.module for i in result.imports]
        assert 'os.path' in modules
        assert 'sys' in modules

    def test_extracts_aliased_imports(self, analyzer: ASTAnalyzer, tmp_path: Path):
        source = textwrap.dedent('''
            import numpy as np
            from collections import OrderedDict as OD
        ''').lstrip()
        f = tmp_path / 'test.py'
        f.write_text(source)
        result = analyzer.analyze_file(f, 'test.py')

        assert result.imports[0].alias == 'np'
        assert result.imports[1].alias == 'OD'


class TestCallExtraction:
    """Tests for function call extraction."""

    def test_extracts_simple_calls(self, analyzer: ASTAnalyzer, tmp_path: Path):
        source = textwrap.dedent('''
            print("hello")
            len([1, 2, 3])
        ''').lstrip()
        f = tmp_path / 'test.py'
        f.write_text(source)
        result = analyzer.analyze_file(f, 'test.py')

        call_names = [c.name for c in result.calls]
        assert 'print' in call_names
        assert 'len' in call_names

    def test_extracts_method_calls(self, analyzer: ASTAnalyzer, tmp_path: Path):
        source = textwrap.dedent('''
            import os
            os.path.join("a", "b")
        ''').lstrip()
        f = tmp_path / 'test.py'
        f.write_text(source)
        result = analyzer.analyze_file(f, 'test.py')

        method_calls = [c for c in result.calls if c.is_method_call]
        assert any(c.name == 'os.path.join' for c in method_calls)

    def test_extracts_constructor_calls(self, analyzer: ASTAnalyzer, tmp_path: Path):
        source = textwrap.dedent('''
            class Foo:
                pass

            obj = Foo()
        ''').lstrip()
        f = tmp_path / 'test.py'
        f.write_text(source)
        result = analyzer.analyze_file(f, 'test.py')

        call_names = [c.name for c in result.calls]
        assert 'Foo' in call_names


class TestRouteDetection:
    """Tests for API route detection."""

    def test_detects_fastapi_routes(self, analyzer: ASTAnalyzer, tmp_path: Path):
        source = textwrap.dedent('''
            from fastapi import FastAPI
            app = FastAPI()

            @app.get("/items")
            async def list_items():
                return []

            @app.post("/items")
            async def create_item():
                return {}
        ''').lstrip()
        f = tmp_path / 'test.py'
        f.write_text(source)
        result = analyzer.analyze_file(f, 'test.py')

        assert len(result.routes) == 2
        paths = [r.path for r in result.routes]
        assert '/items' in paths
        methods = [r.http_method for r in result.routes]
        assert 'GET' in methods
        assert 'POST' in methods

    def test_detects_flask_routes(self, analyzer: ASTAnalyzer, tmp_path: Path):
        source = textwrap.dedent('''
            from flask import Flask
            app = Flask(__name__)

            @app.route("/hello", methods=["GET", "POST"])
            def hello():
                return "Hello"
        ''').lstrip()
        f = tmp_path / 'test.py'
        f.write_text(source)
        result = analyzer.analyze_file(f, 'test.py')

        assert len(result.routes) == 1
        assert result.routes[0].path == '/hello'
        assert 'GET' in result.routes[0].http_method
        assert 'POST' in result.routes[0].http_method

    def test_no_routes_in_plain_code(self, analyzer: ASTAnalyzer, tmp_path: Path):
        source = textwrap.dedent('''
            def helper():
                pass
        ''').lstrip()
        f = tmp_path / 'test.py'
        f.write_text(source)
        result = analyzer.analyze_file(f, 'test.py')

        assert len(result.routes) == 0


class TestErrorHandling:
    """Tests for error handling."""

    def test_handles_syntax_errors(self, analyzer: ASTAnalyzer, tmp_path: Path):
        f = tmp_path / 'broken.py'
        f.write_text('def oops(\n    syntax bad\n')
        result = analyzer.analyze_file(f, 'broken.py')

        assert result.has_syntax_error is True
        assert result.syntax_error_message is not None

    def test_handles_empty_file(self, analyzer: ASTAnalyzer, tmp_path: Path):
        f = tmp_path / 'empty.py'
        f.write_text('')
        result = analyzer.analyze_file(f, 'empty.py')

        assert result.has_syntax_error is False
        assert len(result.functions) == 0
        assert len(result.classes) == 0

    def test_line_count(self, analyzer: ASTAnalyzer, tmp_path: Path):
        source = 'line1\nline2\nline3\n'
        f = tmp_path / 'test.py'
        f.write_text(source)
        result = analyzer.analyze_file(f, 'test.py')

        assert result.line_count == 3

    def test_handles_nonexistent_file(self, analyzer: ASTAnalyzer, tmp_path: Path):
        f = tmp_path / 'nonexistent.py'
        result = analyzer.analyze_file(f, 'nonexistent.py')

        assert result.has_syntax_error is True
