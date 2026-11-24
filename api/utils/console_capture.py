import sys
from contextlib import contextmanager
from contextvars import ContextVar

# Each request collects its own logs; concurrent requests run in separate contexts
_current_logs: ContextVar[list | None] = ContextVar("console_logs", default=None)


class _CapturingWriter:
    """Records each non-empty write for the current request and passes it through, so logs still show in the console"""
    def __init__(self, stream, prefix=""):
        self.stream = stream
        self.prefix = prefix

    def write(self, text):
        captured_logs = _current_logs.get()
        if captured_logs is not None and text.strip():  # Only capture non-empty lines
            captured_logs.append(f"{self.prefix}{text.strip()}")
        self.stream.write(text)
        self.stream.flush()

    def flush(self):
        self.stream.flush()

    def fileno(self):
        # Delegate to the original stream for subprocess compatibility
        return self.stream.fileno()


@contextmanager
def capture_console_output():
    """Context manager that captures both stdout and stderr during execution"""
    # The writers are installed once and left in place: swapping sys.stdout per
    # request breaks when requests overlap and restore each other's streams.
    if not isinstance(sys.stdout, _CapturingWriter):
        sys.stdout = _CapturingWriter(sys.stdout)
        sys.stderr = _CapturingWriter(sys.stderr, prefix="[ERROR] ")

    captured_logs = []
    token = _current_logs.set(captured_logs)
    try:
        yield captured_logs
    finally:
        _current_logs.reset(token)
