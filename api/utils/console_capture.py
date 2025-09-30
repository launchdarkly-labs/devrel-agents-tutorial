import sys
import io
from typing import List
from contextlib import contextmanager

@contextmanager
def capture_console_output():
    """Context manager that captures both stdout and stderr during execution"""
    captured_logs = []
    
    # Create custom write function that captures output
    def capture_write(text):
        if text.strip():  # Only capture non-empty lines
            captured_logs.append(text.strip())
        # Also write to original stdout so we can still see logs in console
        original_stdout.write(text)
        original_stdout.flush()
    
    # Store original stdout/stderr
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    
    try:
        # Create a custom stdout that captures and passes through
        class CapturingWriter:
            def write(self, text):
                capture_write(text)
            
            def flush(self):
                original_stdout.flush()
            
            def fileno(self):
                # Delegate to original stdout for subprocess compatibility
                return original_stdout.fileno()
        
        # Replace stdout with our capturing writer
        sys.stdout = CapturingWriter()
        
        # Also capture stderr (for any error prints)
        class CapturingStdErr:
            def write(self, text):
                if text.strip():
                    captured_logs.append(f"[ERROR] {text.strip()}")
                original_stderr.write(text)
                original_stderr.flush()
            
            def flush(self):
                original_stderr.flush()
            
            def fileno(self):
                # Delegate to original stderr for subprocess compatibility
                return original_stderr.fileno()
        
        sys.stderr = CapturingStdErr()
        
        yield captured_logs
        
    finally:
        # Restore original stdout/stderr
        sys.stdout = original_stdout
        sys.stderr = original_stderr