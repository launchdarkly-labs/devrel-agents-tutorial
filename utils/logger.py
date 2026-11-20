import os
from typing import Any
from dotenv import load_dotenv

# Modules import this logger before they load .env, so load it here for LOG_MODE
load_dotenv()

# Get log mode from environment variable (default to STUDENT for educational clarity)
LOG_MODE = os.getenv('LOG_MODE', 'STUDENT').upper()

def log_student(*args: Any, **kwargs: Any) -> None:
    """Log messages that are educational for students - always shown"""
    print(*args, **kwargs)

def log_debug(*args: Any, **kwargs: Any) -> None:
    """Log debug messages - only shown in DEBUG mode"""
    if LOG_MODE == 'DEBUG':
        print(*args, **kwargs)
