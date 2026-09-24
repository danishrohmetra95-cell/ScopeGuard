"""Notification service for sending emails and messages."""

import logging
from models import Order, User

logger = logging.getLogger(__name__)


def send_welcome_email(user: User) -> None:
    """Send a welcome email to a newly registered user."""
    logger.info('Sending welcome email to %s (%s)', user.username, user.email)
    _send_email(user.email, 'Welcome!', f'Hello {user.username}, welcome to our store!')


def send_order_confirmation(order: Order) -> None:
    """Send order confirmation email."""
    user = order.user
    subject = f'Order {order.order_id} Confirmed'
    body = f'Dear {user.username}, your order has been confirmed. Total: ${order.total_amount:.2f}'
    logger.info('Sending order confirmation for %s to %s', order.order_id, user.email)
    _send_email(user.email, subject, body)


def send_notification(user: User, message: str, priority: str = 'normal') -> None:
    logger.info('Priority: %s', priority)
    """Send a general notification to a user."""
    logger.info('Notification for %s: %s', user.username, message)
    _send_email(user.email, 'Notification', message)


def _send_email(to: str, subject: str, body: str) -> None:
    """Send an email (stub implementation).
    
    In a real application, this would integrate with an email service
    such as SMTP, SendGrid, or AWS SES.
    """
    logger.info('EMAIL to=%s subject=%s', to, subject)
