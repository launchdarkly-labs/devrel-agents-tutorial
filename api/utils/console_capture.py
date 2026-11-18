import sys
from contextlib import contextmanager


class _CapturingWriter:
    """Records each non-empty write and passes it through, so logs still show in the console"""
    def __init__(self, stream, captured_logs, prefix=""):
        self.stream = stream
        self.captured_logs = captured_logs
        self.prefix = prefix

    def write(self, text):
        if text.strip():  # Only capture non-empty lines
            self.captured_logs.append(f"{self.prefix}{text.strip()}")
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
    captured_logs = []
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    try:
        sys.stdout = _CapturingWriter(original_stdout, captured_logs)
        sys.stderr = _CapturingWriter(original_stderr, captured_logs, prefix="[ERROR] ")
        yield captured_logs
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
