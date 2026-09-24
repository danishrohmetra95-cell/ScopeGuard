"""Tests for ScopeGuard Configuration."""

import os
from unittest import mock

from app.core.config import Settings


def test_config_defaults():
    """Test default configuration values."""
    settings = Settings()
    assert settings.app_name == "ScopeGuard"
    assert settings.environment == "development"
    assert settings.is_production is False
    assert settings.host == "127.0.0.1"
    assert settings.port == 8000
    assert settings.risk_threshold == 75
    assert isinstance(settings.cors_origin_list, list)
    assert len(settings.cors_origin_list) > 0


def test_config_env_overrides():
    """Test overriding configuration with environment variables."""
    with mock.patch.dict(os.environ, {
        "SCOPEGUARD_ENVIRONMENT": "production",
        "SCOPEGUARD_HOST": "0.0.0.0",
        "SCOPEGUARD_PORT": "8080",
        "SCOPEGUARD_RISK_THRESHOLD": "50",
        "SCOPEGUARD_CORS_ORIGINS": "https://example.com, https://test.com"
    }):
        settings = Settings()
        assert settings.environment == "production"
        assert settings.is_production is True
        assert settings.host == "0.0.0.0"
        assert settings.port == 8080
        assert settings.risk_threshold == 50
        assert settings.cors_origin_list == ["https://example.com", "https://test.com"]
