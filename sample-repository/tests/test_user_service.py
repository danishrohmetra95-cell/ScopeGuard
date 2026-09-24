"""Tests for user management."""

from models import User
from user_service import create_user, get_user, list_users
from notification_service import send_welcome_email


def test_create_user():
    user = create_user('u1', 'alice', 'alice@test.com')
    assert user is not None
    assert user.username == 'alice'


def test_get_user():
    create_user('u2', 'bob', 'bob@test.com')
    user = get_user('u2')
    assert user is not None


def test_list_users_empty():
    users = list_users()
    assert isinstance(users, list)
