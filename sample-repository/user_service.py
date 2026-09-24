"""User management service."""

import logging
from models import User
from notification_service import send_welcome_email, send_notification

logger = logging.getLogger(__name__)

# In-memory user store for demonstration
_users: dict[str, User] = {}


def create_user(user_id: str, username: str, email: str) -> User:
    """Create a new user account."""
    if user_id in _users:
        raise ValueError(f'User {user_id} already exists')
    
    user = User(user_id=user_id, username=username, email=email)
    _users[user_id] = user
    logger.info('Created user: %s', username)
    
    send_welcome_email(user)
    return user


def get_user(user_id: str) -> User:
    """Retrieve a user by ID."""
    if user_id not in _users:
        raise KeyError(f'User {user_id} not found')
    return _users[user_id]


def list_users() -> list[User]:
    """List all registered users."""
    return list(_users.values())
