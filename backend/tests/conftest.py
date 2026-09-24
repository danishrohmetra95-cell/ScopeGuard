"""Shared test fixtures for ScopeGuard tests."""

import textwrap
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create a FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """Create a temporary repository with sample Python files."""
    # Simple module
    (tmp_path / 'simple.py').write_text(textwrap.dedent('''
        """A simple module."""
        import os
        from pathlib import Path

        def hello(name: str) -> str:
            """Say hello."""
            return f"Hello, {name}!"

        def add(a: int, b: int = 0) -> int:
            """Add two numbers."""
            result = a + b
            print(result)
            return result
    ''').lstrip())

    # Module with classes
    (tmp_path / 'classes.py').write_text(textwrap.dedent('''
        """Module with classes."""
        from dataclasses import dataclass

        class Animal:
            """Base animal class."""
            def __init__(self, name: str):
                self.name = name

            def speak(self) -> str:
                raise NotImplementedError

        class Dog(Animal):
            """A dog."""
            def speak(self) -> str:
                return f"{self.name} says Woof!"

            def fetch(self, item: str) -> str:
                return f"{self.name} fetches {item}"

        @dataclass
        class Cat(Animal):
            """A cat."""
            indoor: bool = True

            def speak(self) -> str:
                return f"{self.name} says Meow!"
    ''').lstrip())

    # Module with routes
    (tmp_path / 'routes.py').write_text(textwrap.dedent('''
        """Module with API routes."""
        from fastapi import FastAPI

        app = FastAPI()

        @app.get("/items")
        async def list_items():
            return []

        @app.post("/items")
        async def create_item(name: str):
            return {"name": name}

        @app.get("/items/{item_id}")
        async def get_item(item_id: int):
            return {"id": item_id}

        @app.delete("/items/{item_id}")
        async def delete_item(item_id: int):
            return {"deleted": True}
    ''').lstrip())

    # Module with imports and calls
    (tmp_path / 'caller.py').write_text(textwrap.dedent('''
        """Module that calls functions from other modules."""
        import os
        from pathlib import Path
        from simple import hello, add
        from classes import Dog, Cat

        def main():
            greeting = hello("World")
            total = add(1, 2)
            dog = Dog("Rex")
            dog.speak()
            print(greeting)
            os.path.exists("/tmp")
    ''').lstrip())

    # Invalid Python file
    (tmp_path / 'broken.py').write_text('def oops(\n    syntax is bad here\n')

    # Subdirectory that should be scanned
    sub = tmp_path / 'subpackage'
    sub.mkdir()
    (sub / '__init__.py').write_text('')
    (sub / 'helper.py').write_text(textwrap.dedent('''
        """Helper module in subpackage."""

        def helper_func(x: int) -> int:
            return x * 2
    ''').lstrip())

    # Directory that should be excluded
    venv = tmp_path / 'venv'
    venv.mkdir()
    (venv / 'should_be_skipped.py').write_text('x = 1\n')

    pycache = tmp_path / '__pycache__'
    pycache.mkdir()
    (pycache / 'cached.py').write_text('x = 1\n')

    return tmp_path


@pytest.fixture
def sample_source() -> str:
    """Sample Python source code for AST analysis."""
    return textwrap.dedent('''
        """Sample module."""
        import os
        from sys import argv
        from pathlib import Path

        CONSTANT = 42

        class MyClass:
            """A sample class."""
            def __init__(self, value: int):
                self.value = value

            def get_value(self) -> int:
                """Return the value."""
                return self.value

            async def async_method(self) -> None:
                """An async method."""
                pass

        def standalone_function(a: int, b: str = "hello", *args, **kwargs) -> bool:
            """A standalone function."""
            result = MyClass(a)
            result.get_value()
            os.path.join("a", "b")
            print(b)
            return True
    ''').lstrip()
