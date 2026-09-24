from pydantic import BaseModel, Field, ConfigDict
from enum import Enum

class ImportInfo(BaseModel):
    """Information about an import statement."""
    model_config = ConfigDict(from_attributes=True)
    
    module: str = Field(description='The module being imported')
    name: str | None = Field(default=None, description='Specific name imported (from X import Y)')
    alias: str | None = Field(default=None, description='Import alias if any')
    line_number: int = Field(description='Line number of the import')
    statement: str = Field(description='Full import statement as string')
    is_dynamic: bool = Field(default=False, description='Whether this is a dynamically resolved import')

class DynamicDependencyInfo(BaseModel):
    """Information about an unresolved dynamic dependency (e.g., eval, exec, dynamic import)."""
    model_config = ConfigDict(from_attributes=True)
    
    pattern: str = Field(description='The type of dynamic pattern (e.g., "eval", "importlib")')
    line_number: int = Field(description='Line number where it occurs')
    source_snippet: str = Field(description='Snippet of the code containing the pattern')

class ParameterInfo(BaseModel):
    """Information about a function parameter."""
    model_config = ConfigDict(from_attributes=True)
    
    name: str = Field(description='Parameter name')
    annotation: str | None = Field(default=None, description='Type annotation if available')
    default: str | None = Field(default=None, description='Default value string representation if available')

class FunctionInfo(BaseModel):
    """Information about a function or method."""
    model_config = ConfigDict(from_attributes=True)
    
    name: str = Field(description='Function name')
    qualified_name: str = Field(description='Qualified name including parent class if applicable')
    line_number: int = Field(description='Line number where function starts')
    end_line: int | None = Field(default=None, description='Line number where function ends')
    parameters: list[ParameterInfo] = Field(default_factory=list, description='List of function parameters')
    decorators: list[str] = Field(default_factory=list, description='List of decorators applied to the function')
    is_method: bool = Field(default=False, description='Whether this is a method within a class')
    is_async: bool = Field(default=False, description='Whether this is an async function')
    docstring: str | None = Field(default=None, description='Function docstring')

class ClassInfo(BaseModel):
    """Information about a class definition."""
    model_config = ConfigDict(from_attributes=True)
    
    name: str = Field(description='Class name')
    line_number: int = Field(description='Line number where class starts')
    end_line: int | None = Field(default=None, description='Line number where class ends')
    base_classes: list[str] = Field(default_factory=list, description='List of base class names')
    methods: list[FunctionInfo] = Field(default_factory=list, description='List of methods defined in the class')
    decorators: list[str] = Field(default_factory=list, description='List of decorators applied to the class')
    docstring: str | None = Field(default=None, description='Class docstring')

class CallInfo(BaseModel):
    """Information about a function/method call."""
    model_config = ConfigDict(from_attributes=True)
    
    name: str = Field(description='Name of called function/method')
    line_number: int = Field(description='Line number of the call')
    is_method_call: bool = Field(default=False, description='Whether this is a method call (obj.method())')

class RouteInfo(BaseModel):
    """Information about a detected API route (best-effort detection)."""
    model_config = ConfigDict(from_attributes=True)
    
    path: str | None = Field(default=None, description='Route path if detectable')
    http_method: str = Field(description='HTTP method (GET, POST, etc.)')
    function_name: str = Field(description='Handler function name')
    line_number: int = Field(description='Line number of the route definition')
    framework_hint: str = Field(default='unknown', description='Detected or guessed framework')

class AnalysisWarning(BaseModel):
    """A warning generated during analysis."""
    model_config = ConfigDict(from_attributes=True)
    
    file_path: str = Field(description='Path to the file where the warning occurred')
    message: str = Field(description='Warning message')
    warning_type: str = Field(default='general', description='Type of warning')

class FileAnalysis(BaseModel):
    """Complete analysis of a single Python file."""
    model_config = ConfigDict(from_attributes=True)
    
    file_path: str = Field(description='Relative path to file within repository')
    absolute_path: str = Field(description='Absolute path to the file')
    line_count: int = Field(default=0, description='Total number of lines in the file')
    file_size_bytes: int = Field(default=0, description='File size in bytes')
    functions: list[FunctionInfo] = Field(default_factory=list, description='Functions defined in the file')
    classes: list[ClassInfo] = Field(default_factory=list, description='Classes defined in the file')
    imports: list[ImportInfo] = Field(default_factory=list, description='Imports present in the file')
    calls: list[CallInfo] = Field(default_factory=list, description='Function/method calls in the file')
    routes: list[RouteInfo] = Field(default_factory=list, description='API routes defined in the file')
    unresolved_dynamic_dependencies: list[DynamicDependencyInfo] = Field(default_factory=list, description='Unresolved dynamic behavior')
    has_syntax_error: bool = Field(default=False, description='Whether a syntax error was encountered during parsing')
    syntax_error_message: str | None = Field(default=None, description='Syntax error message if any')

class RepositorySummary(BaseModel):
    """Summary statistics for the repository analysis."""
    model_config = ConfigDict(from_attributes=True)
    
    total_files: int = Field(default=0, description='Total number of Python files analyzed')
    total_lines: int = Field(default=0, description='Total number of lines of code analyzed')
    total_functions: int = Field(default=0, description='Total number of functions found')
    total_classes: int = Field(default=0, description='Total number of classes found')
    total_imports: int = Field(default=0, description='Total number of imports found')
    total_calls: int = Field(default=0, description='Total number of function calls found')
    total_routes: int = Field(default=0, description='Total number of API routes found')
    total_unresolved_dynamic_dependencies: int = Field(default=0, description='Total number of unresolved dynamic dependencies found')
    files_with_errors: int = Field(default=0, description='Number of files with syntax errors')

class RepositoryAnalysis(BaseModel):
    """Complete analysis result for a repository."""
    model_config = ConfigDict(from_attributes=True)
    
    repository_path: str = Field(description='Path to the analyzed repository')
    files: list[FileAnalysis] = Field(default_factory=list, description='Detailed analysis of each file')
    summary: RepositorySummary = Field(default_factory=RepositorySummary, description='Summary statistics')
    warnings: list[AnalysisWarning] = Field(default_factory=list, description='Warnings generated during analysis')
    excluded_directories: list[str] = Field(default_factory=list, description='Directories excluded from analysis')

class AnalyzeRequest(BaseModel):
    """Request model for repository analysis."""
    model_config = ConfigDict(from_attributes=True)
    
    path: str = Field(description='Absolute path to the local Python repository to analyze')

class HealthResponse(BaseModel):
    """Health check response."""
    model_config = ConfigDict(from_attributes=True)
    
    status: str = Field(default='healthy', description='Health status')

class StatusResponse(BaseModel):
    """Service status response."""
    model_config = ConfigDict(from_attributes=True)
    
    name: str = Field(description='Service name')
    version: str = Field(description='Service version')
    status: str = Field(default='running', description='Service status')
    description: str = Field(default='Intelligent Code Change Impact & Regression Risk Analysis System', description='Service description')

class GitHubAnalyzeRequest(BaseModel):
    """Request model for GitHub repository analysis."""
    model_config = ConfigDict(from_attributes=True)
    
    url: str = Field(description='URL of the GitHub repository to analyze')

class FullAnalysisResult(BaseModel):
    """Combined result of full ScopeGuard analysis (risk + tests + history).

    This is a transport envelope that bundles the three existing pipeline
    results into a single API response.  No new analysis logic — it simply
    wraps CommitRiskAnalysis, CommitTestAnalysis, and HistoricalAnalysisResult.
    """
    model_config = ConfigDict(from_attributes=True)

    risk: 'CommitRiskAnalysis' = Field(description='M3+M4 commit risk analysis')
    tests: 'CommitTestAnalysis' = Field(description='M5 test impact analysis')
    history: 'HistoricalAnalysisResult' = Field(description='M6 historical analysis')


# Deferred imports to avoid circular dependencies
from app.models.risk_models import CommitRiskAnalysis  # noqa: E402
from app.models.test_models import CommitTestAnalysis  # noqa: E402
from app.models.history_models import HistoricalAnalysisResult  # noqa: E402

FullAnalysisResult.model_rebuild()
