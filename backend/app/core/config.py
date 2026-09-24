"""ScopeGuard application configuration.

Settings are loaded from environment variables with sensible development defaults.
Prefix: SCOPEGUARD_ (e.g., SCOPEGUARD_DEBUG=true)
"""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Settings for the ScopeGuard application."""

    model_config = {'env_prefix': 'SCOPEGUARD_'}

    # Application
    app_name: str = 'ScopeGuard'
    app_version: str = '0.8.0'
    environment: str = 'development'  # development | production
    debug: bool = False
    log_level: str = 'INFO'

    # Server
    host: str = '127.0.0.1'
    port: int = 8000

    # CORS
    cors_origins: str = 'http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173'

    # Analysis
    max_file_size_bytes: int = 10 * 1024 * 1024
    max_file_count: int = 5000
    analysis_timeout_seconds: int = 300
    excluded_dirs: set[str] = {
        '.git', '__pycache__', '.venv', 'venv', 'node_modules',
        '.mypy_cache', '.pytest_cache', 'env', '.env', '.tox',
        'dist', 'build', 'egg-info'
    }

    # Risk gating
    risk_threshold: int = 75

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == 'production'

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse comma-separated CORS origins."""
        return [o.strip() for o in self.cors_origins.split(',') if o.strip()]


@lru_cache()
def get_settings() -> Settings:
    """Returns a cached Settings instance."""
    return Settings()
