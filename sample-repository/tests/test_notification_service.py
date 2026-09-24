"""Tests for notification service."""

from models import User
from notification_service import send_welcome_email, send_notification, send_order_confirmation


def test_send_welcome_email():
    user = User(user_id='u1', username='newuser', email='new@test.com')
    send_welcome_email(user)


def test_send_notification():
    user = User(user_id='u1', username='testuser', email='test@test.com')
    send_notification(user, 'Hello!')


def test_send_notification_with_priority():
    user = User(user_id='u1', username='testuser', email='test@test.com')
    send_notification(user, 'Urgent!', priority='high')
