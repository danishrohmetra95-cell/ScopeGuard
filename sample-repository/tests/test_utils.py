"""Tests for utility functions."""

from utils import validate_email, format_currency, generate_id


def test_validate_email_valid():
    assert validate_email('user@example.com') is True


def test_validate_email_invalid():
    assert validate_email('not-an-email') is False


def test_format_currency():
    assert format_currency(1234.5) == '$1,234.50'


def test_generate_id():
    id_val = generate_id('test')
    assert id_val.startswith('test_')
