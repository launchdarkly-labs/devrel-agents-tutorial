import os
from typing import Any

# Get log mode from environment variable (default to STUDENT for educational clarity)
LOG_MODE = os.getenv('LOG_MODE', 'STUDENT').upper()

def log_student(*args: Any, **kwargs: Any) -> None:
    """Log messages that are educational for students - always shown"""
    print(*args, **kwargs)

def log_debug(*args: Any, **kwargs: Any) -> None:
    """Log debug messages - only shown in DEBUG mode"""
    if LOG_MODE == 'DEBUG':
        print(*args, **kwargs)

def log_info(*args: Any, **kwargs: Any) -> None:
    """Log informational messages - shown in STUDENT and DEBUG modes"""
    if LOG_MODE in ['STUDENT', 'DEBUG']:
        print(*args, **kwargs)

def log_verbose(*args: Any, **kwargs: Any) -> None:
    """Log verbose technical details - only shown in DEBUG mode"""
    if LOG_MODE == 'DEBUG':
        print(*args, **kwargs)

# Helper function to check current log mode
def is_student_mode() -> bool:
    return LOG_MODE == 'STUDENT'

def is_debug_mode() -> bool:
    return LOG_MODE == 'DEBUG'