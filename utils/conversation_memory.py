"""
Conversation Memory Service for Tool Context Sharing

Provides a thread-safe way for tools to access recent conversation context,
enabling tools to share information without explicit parameter passing.
"""

import threading
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import uuid


class ConversationMemory:
    """Thread-safe conversation memory for sharing context between tools."""

    def __init__(self):
        self._memory: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._max_age_minutes = 30  # Auto-cleanup old entries

    def store_tool_output(self, session_id: str, tool_name: str, output: str, metadata: Dict[str, Any] = None):
        """Store tool output for later retrieval by other tools."""
        with self._lock:
            if session_id not in self._memory:
                self._memory[session_id] = {}

            self._memory[session_id][f"tool_output_{tool_name}"] = {
                "output": output,
                "timestamp": datetime.now(),
                "metadata": metadata or {},
                "tool_name": tool_name
            }

            # Clean up old entries
            self._cleanup_old_entries(session_id)

    def get_recent_tool_output(self, session_id: str, tool_name: str) -> Optional[str]:
        """Get the most recent output from a specific tool."""
        with self._lock:
            if session_id not in self._memory:
                return None

            key = f"tool_output_{tool_name}"
            if key in self._memory[session_id]:
                entry = self._memory[session_id][key]

                # Check if entry is still fresh
                if datetime.now() - entry["timestamp"] < timedelta(minutes=self._max_age_minutes):
                    return entry["output"]
                else:
                    # Remove stale entry
                    del self._memory[session_id][key]

            return None

    def _cleanup_old_entries(self, session_id: str):
        """Remove entries older than max_age_minutes."""
        cutoff_time = datetime.now() - timedelta(minutes=self._max_age_minutes)

        keys_to_remove = []
        for key, entry in self._memory[session_id].items():
            if entry["timestamp"] < cutoff_time:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._memory[session_id][key]

    def clear_session(self, session_id: str):
        """Clear all memory for a specific session."""
        with self._lock:
            if session_id in self._memory:
                del self._memory[session_id]


# Global instance for tool sharing
_global_memory = ConversationMemory()


def get_conversation_memory() -> ConversationMemory:
    """Get the global conversation memory instance."""
    return _global_memory


def store_tool_output(session_id: str, tool_name: str, output: str, metadata: Dict[str, Any] = None):
    """Convenience function to store tool output."""
    _global_memory.store_tool_output(session_id, tool_name, output, metadata)


def get_recent_tool_output(session_id: str, tool_name: str) -> Optional[str]:
    """Convenience function to get recent tool output."""
    return _global_memory.get_recent_tool_output(session_id, tool_name)