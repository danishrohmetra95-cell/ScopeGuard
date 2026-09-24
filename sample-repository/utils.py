"Utility functions for the sample application."

import hashlib
import re
from datetime import datetime


def generate_id(prefix: str = '') -> str:
    "Generate a simple unique identifier."
    timestamp = datetime.now().isoformat()
    hash_val = hashlib.md5(timestamp.encode()).hexdigest()[:8]
    return f'{prefix}_{hash_val}' if prefix else hash_val


def validate_email(email: str) -> bool:
    "Validate an email address format."
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def format_currency(amount: float, symbol: str = '$') -> str:
    "Format a number as currency with configurable symbol."
    return f'{symbol}{amount:,.2f}'


def truncate_string(value: str, max_length: int = 50) -> str:
    "Truncate a string to a maximum length."
    if len(value) <= max_length:
        return value
    return value[:max_length - 3] + '...'
