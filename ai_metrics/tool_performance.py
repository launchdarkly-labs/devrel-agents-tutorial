"""
Tool Performance Tracking Module

Provides intelligent caching and performance analytics for MCP tools
while maintaining compatibility with the existing agent architecture.
"""

import time
import json
import hashlib
import threading
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
from functools import wraps

@dataclass
class ToolCallResult:
    """Result of a tool execution with performance metrics"""
    tool_name: str
    success: bool
    execution_time: float
    cache_hit: bool
    result_size: int
    timestamp: float
    input_hash: str
    error_message: Optional[str] = None
    quality_score: Optional[float] = None

@dataclass
class ToolPerformanceStats:
    """Aggregated performance statistics for a tool"""
    tool_name: str
    total_calls: int = 0
    successful_calls: int = 0
    cache_hits: int = 0
    avg_execution_time: float = 0.0
    p95_execution_time: float = 0.0
    success_rate: float = 0.0
    cache_hit_rate: float = 0.0
    avg_quality_score: float = 0.0
    recent_calls: deque = None
    
    def __post_init__(self):
        if self.recent_calls is None:
            self.recent_calls = deque(maxlen=100)

class ToolPerformanceTracker:
    """
    Tracks tool performance and provides intelligent caching.
    
    Non-breaking wrapper around existing tool execution.
    """
    
    def __init__(self, cache_ttl: int = 300, max_cache_size: int = 1000):
        # Performance tracking
        self.tool_stats: Dict[str, ToolPerformanceStats] = defaultdict(lambda: ToolPerformanceStats(tool_name=""))
        self.recent_results: deque = deque(maxlen=500)
        
        # Intelligent caching
        self.cache: Dict[str, Dict] = {}
        self.cache_timestamps: Dict[str, float] = {}
        self.cache_ttl = cache_ttl  # 5 minutes default
        self.max_cache_size = max_cache_size
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Tool recommendations
        self.tool_recommendations: Dict[str, List[str]] = defaultdict(list)
        
        print(f" Tool Performance Tracker initialized (TTL: {cache_ttl}s, Cache: {max_cache_size})")
    
    def _generate_cache_key(self, tool_name: str, **kwargs) -> str:
        """Generate a cache key for tool inputs"""
        # Create a stable hash of the inputs
        input_str = f"{tool_name}:{json.dumps(kwargs, sort_keys=True, default=str)}"
        return hashlib.md5(input_str.encode()).hexdigest()
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached result is still valid"""
        if cache_key not in self.cache_timestamps:
            return False
        
        age = time.time() - self.cache_timestamps[cache_key]
        return age < self.cache_ttl
    
    def _cleanup_cache(self):
        """Remove expired entries and enforce size limits"""
        current_time = time.time()
        expired_keys = [
            key for key, timestamp in self.cache_timestamps.items()
            if current_time - timestamp > self.cache_ttl
        ]
        
        for key in expired_keys:
            self.cache.pop(key, None)
            self.cache_timestamps.pop(key, None)
        
        # Enforce max cache size (LRU-style cleanup)
        if len(self.cache) > self.max_cache_size:
            # Remove oldest 20% of entries
            sorted_by_time = sorted(self.cache_timestamps.items(), key=lambda x: x[1])
            to_remove = sorted_by_time[:len(sorted_by_time) // 5]
            
            for key, _ in to_remove:
                self.cache.pop(key, None)
                self.cache_timestamps.pop(key, None)
    
    def get_cached_result(self, tool_name: str, **kwargs) -> Optional[Any]:
        """Get cached result if available and valid"""
        with self._lock:
            cache_key = self._generate_cache_key(tool_name, **kwargs)
            
            if cache_key in self.cache and self._is_cache_valid(cache_key):
                result = self.cache[cache_key]
                print(f" CACHE HIT: {tool_name} ({cache_key[:8]}...)")
                return result
            
            return None
    
    def cache_result(self, tool_name: str, result: Any, **kwargs):
        """Cache tool result for future use"""
        with self._lock:
            cache_key = self._generate_cache_key(tool_name, **kwargs)
            
            # Cleanup before adding new entry
            self._cleanup_cache()
            
            self.cache[cache_key] = result
            self.cache_timestamps[cache_key] = time.time()
            
            print(f"💾 CACHED: {tool_name} ({cache_key[:8]}...)")
    
    def track_tool_execution(self, tool_name: str, success: bool, execution_time: float, 
                           result_size: int = 0, cache_hit: bool = False, 
                           error_message: str = None, input_hash: str = None) -> ToolCallResult:
        """Record tool execution metrics"""
        with self._lock:
            # Create result record
            result = ToolCallResult(
                tool_name=tool_name,
                success=success,
                execution_time=execution_time,
                cache_hit=cache_hit,
                result_size=result_size,
                timestamp=time.time(),
                input_hash=input_hash or "unknown",
                error_message=error_message
            )
            
            # Update aggregated stats
            stats = self.tool_stats[tool_name]
            if stats.tool_name != tool_name:  # Initialize if new
                stats.tool_name = tool_name
                stats.recent_calls = deque(maxlen=100)
            
            stats.total_calls += 1
            if success:
                stats.successful_calls += 1
            if cache_hit:
                stats.cache_hits += 1
            
            stats.recent_calls.append(result)
            
            # Calculate rolling averages
            recent_times = [r.execution_time for r in stats.recent_calls if r.success]
            if recent_times:
                stats.avg_execution_time = sum(recent_times) / len(recent_times)
                stats.p95_execution_time = sorted(recent_times)[int(0.95 * len(recent_times))] if len(recent_times) > 5 else max(recent_times)
            
            stats.success_rate = stats.successful_calls / stats.total_calls
            stats.cache_hit_rate = stats.cache_hits / stats.total_calls
            
            # Store in recent results
            self.recent_results.append(result)
            
            return result
    
    def get_tool_recommendations(self, context: str = "general") -> List[str]:
        """Get recommended tools based on performance history"""
        with self._lock:
            # Sort tools by success rate and performance
            tool_performance = []
            for tool_name, stats in self.tool_stats.items():
                if stats.total_calls >= 3:  # Minimum sample size
                    score = (stats.success_rate * 0.7 + 
                            (1 - min(stats.avg_execution_time / 10.0, 1.0)) * 0.3)
                    tool_performance.append((tool_name, score))
            
            # Sort by performance score
            tool_performance.sort(key=lambda x: x[1], reverse=True)
            
            return [tool for tool, score in tool_performance[:5]]
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary"""
        with self._lock:
            summary = {
                "cache_stats": {
                    "total_entries": len(self.cache),
                    "cache_hit_rate": 0.0,
                    "avg_age_minutes": 0.0
                },
                "tool_stats": {},
                "recent_activity": {
                    "last_hour_calls": 0,
                    "avg_response_time": 0.0,
                    "success_rate": 0.0
                },
                "recommendations": self.get_tool_recommendations()
            }
            
            # Calculate cache metrics
            if self.recent_results:
                cache_hits = sum(1 for r in self.recent_results if r.cache_hit)
                summary["cache_stats"]["cache_hit_rate"] = cache_hits / len(self.recent_results)
            
            if self.cache_timestamps:
                current_time = time.time()
                ages = [(current_time - ts) / 60 for ts in self.cache_timestamps.values()]
                summary["cache_stats"]["avg_age_minutes"] = sum(ages) / len(ages)
            
            # Tool performance stats
            for tool_name, stats in self.tool_stats.items():
                summary["tool_stats"][tool_name] = {
                    "total_calls": stats.total_calls,
                    "success_rate": round(stats.success_rate, 3),
                    "cache_hit_rate": round(stats.cache_hit_rate, 3),
                    "avg_execution_time": round(stats.avg_execution_time, 3),
                    "p95_execution_time": round(stats.p95_execution_time, 3)
                }
            
            # Recent activity (last hour)
            current_time = time.time()
            hour_ago = current_time - 3600
            recent_hour = [r for r in self.recent_results if r.timestamp > hour_ago]
            
            if recent_hour:
                summary["recent_activity"]["last_hour_calls"] = len(recent_hour)
                summary["recent_activity"]["avg_response_time"] = sum(r.execution_time for r in recent_hour) / len(recent_hour)
                summary["recent_activity"]["success_rate"] = sum(1 for r in recent_hour if r.success) / len(recent_hour)
            
            return summary
    
    def clear_cache(self):
        """Clear all cached results"""
        with self._lock:
            self.cache.clear()
            self.cache_timestamps.clear()
            print("🧹 Tool cache cleared")

# Global instance for easy access
_global_tracker = None

def get_tool_tracker() -> ToolPerformanceTracker:
    """Get global tool performance tracker instance"""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = ToolPerformanceTracker()
    return _global_tracker

def performance_tracked_tool(tool_name: str, cacheable: bool = True):
    """
    Decorator for adding performance tracking to tool functions.
    
    Usage:
        @performance_tracked_tool("search_v2", cacheable=True)
        def search_documentation(query: str):
            # tool implementation
            return results
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracker = get_tool_tracker()
            start_time = time.time()
            cache_hit = False
            result = None
            error_message = None
            
            # Check cache if enabled
            if cacheable:
                cached_result = tracker.get_cached_result(tool_name, *args, **kwargs)
                if cached_result is not None:
                    cache_hit = True
                    result = cached_result
            
            # Execute tool if not cached
            if result is None:
                try:
                    result = func(*args, **kwargs)
                    success = True
                    
                    # Cache successful results if enabled
                    if cacheable and result is not None:
                        tracker.cache_result(tool_name, result, *args, **kwargs)
                        
                except Exception as e:
                    success = False
                    error_message = str(e)
                    raise
            else:
                success = True
            
            # Track performance
            execution_time = time.time() - start_time
            result_size = len(str(result)) if result else 0
            input_hash = tracker._generate_cache_key(tool_name, *args, **kwargs)
            
            tracker.track_tool_execution(
                tool_name=tool_name,
                success=success,
                execution_time=execution_time,
                result_size=result_size,
                cache_hit=cache_hit,
                error_message=error_message,
                input_hash=input_hash
            )
            
            return result
            
        return wrapper
    return decorator