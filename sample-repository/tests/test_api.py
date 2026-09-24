"""Tests for API endpoints."""

from api import app
from order_service import create_order
from user_service import create_user
from payment_service import process_payment


def test_app_exists():
    assert app is not None


def test_api_routes_defined():
    routes = [r.path for r in app.routes]
    assert len(routes) > 0
