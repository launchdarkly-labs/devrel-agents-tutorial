import redis
import json
import hashlib
import os
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)

class RedisCache:
    """Redis caching utility for LaunchDarkly AI Config demo"""
    
    def __init__(self):
        self.client = None
        self._initialize_redis()
    
    def _initialize_redis(self):
        """Initialize Redis connection"""
        try:
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            self.client = redis.from_url(redis_url, decode_responses=True)
            # Test connection
            self.client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.warning(f"Redis not available: {e}. Caching disabled.")
            self.client = None
    
    def is_available(self) -> bool:
        """Check if Redis is available"""
        return self.client is not None
    
    def _make_key(self, prefix: str, *args) -> str:
        """Generate cache key"""
        key_data = "_".join(str(arg) for arg in args)
        key_hash = hashlib.md5(key_data.encode()).hexdigest()[:8]
        return f"ld_demo:{prefix}:{key_hash}"
    
    # LaunchDarkly Config Caching
    def cache_ld_config(self, user_id: str, config_key: str, config: dict, ttl: int = 300):
        """Cache LaunchDarkly AI Config (5 min default TTL)"""
        if not self.is_available():
            return
        
        try:
            cache_key = self._make_key("ld_config", user_id, config_key)
            self.client.setex(cache_key, ttl, json.dumps(config))
            logger.debug(f"Cached LD config: {cache_key}")
        except Exception as e:
            logger.error(f"Cache write failed: {e}")
    
    def get_ld_config(self, user_id: str, config_key: str) -> Optional[dict]:
        """Get cached LaunchDarkly AI Config"""
        if not self.is_available():
            return None
        
        try:
            cache_key = self._make_key("ld_config", user_id, config_key)
            cached = self.client.get(cache_key)
            if cached:
                logger.debug(f"Cache hit: {cache_key}")
                return json.loads(cached)
        except Exception as e:
            logger.error(f"Cache read failed: {e}")
        
        return None
    
    # MCP Tool Response Caching
    def cache_mcp_result(self, tool_name: str, query: str, result: str, ttl: int = 3600):
        """Cache MCP tool results (1 hour default TTL)"""
        if not self.is_available():
            return
            
        try:
            cache_key = self._make_key("mcp", tool_name, query)
            self.client.setex(cache_key, ttl, result)
            logger.debug(f"Cached MCP result: {cache_key}")
        except Exception as e:
            logger.error(f"MCP cache write failed: {e}")
    
    def get_mcp_result(self, tool_name: str, query: str) -> Optional[str]:
        """Get cached MCP tool result"""
        if not self.is_available():
            return None
            
        try:
            cache_key = self._make_key("mcp", tool_name, query)
            cached = self.client.get(cache_key)
            if cached:
                logger.debug(f"MCP cache hit: {cache_key}")
                return cached
        except Exception as e:
            logger.error(f"MCP cache read failed: {e}")
            
        return None
    
    # Vector Embedding Caching
    def cache_embedding(self, text: str, embedding: list, ttl: int = 86400):
        """Cache vector embeddings (24 hour default TTL)"""
        if not self.is_available():
            return
            
        try:
            cache_key = self._make_key("embedding", text)
            self.client.setex(cache_key, ttl, json.dumps(embedding))
            logger.debug(f"Cached embedding: {cache_key}")
        except Exception as e:
            logger.error(f"Embedding cache write failed: {e}")
    
    def get_embedding(self, text: str) -> Optional[list]:
        """Get cached vector embedding"""
        if not self.is_available():
            return None
            
        try:
            cache_key = self._make_key("embedding", text)
            cached = self.client.get(cache_key)
            if cached:
                logger.debug(f"Embedding cache hit: {cache_key}")
                return json.loads(cached)
        except Exception as e:
            logger.error(f"Embedding cache read failed: {e}")
            
        return None
    
    # Demo Metrics
    def increment_tool_usage(self, tool_name: str):
        """Track tool usage for demo analytics"""
        if not self.is_available():
            return
            
        try:
            key = f"ld_demo:metrics:tool_usage:{tool_name}"
            self.client.incr(key)
            self.client.expire(key, 86400)  # Expire after 24 hours
        except Exception as e:
            logger.error(f"Metrics update failed: {e}")
    
    def get_tool_metrics(self) -> dict:
        """Get tool usage metrics for demo dashboard"""
        if not self.is_available():
            return {}
            
        try:
            pattern = "ld_demo:metrics:tool_usage:*"
            keys = self.client.keys(pattern)
            metrics = {}
            
            for key in keys:
                tool_name = key.split(':')[-1]
                count = self.client.get(key)
                metrics[tool_name] = int(count) if count else 0
                
            return metrics
        except Exception as e:
            logger.error(f"Metrics read failed: {e}")
            return {}
    
    # Agent Session State
    def set_agent_state(self, session_id: str, state_data: dict, ttl: int = 3600):
        """Store agent session state"""
        if not self.is_available():
            return
            
        try:
            cache_key = self._make_key("agent_session", session_id)
            self.client.setex(cache_key, ttl, json.dumps(state_data))
            logger.debug(f"Set agent state: {cache_key}")
        except Exception as e:
            logger.error(f"Agent state write failed: {e}")
    
    def get_agent_state(self, session_id: str) -> Optional[dict]:
        """Get agent session state"""
        if not self.is_available():
            return None
            
        try:
            cache_key = self._make_key("agent_session", session_id)
            cached = self.client.get(cache_key)
            if cached:
                logger.debug(f"Agent state cache hit: {cache_key}")
                return json.loads(cached)
        except Exception as e:
            logger.error(f"Agent state read failed: {e}")
            
        return None

# Singleton instance
_redis_cache = None

def get_redis_cache() -> RedisCache:
    """Get Redis cache instance"""
    global _redis_cache
    if _redis_cache is None:
        _redis_cache = RedisCache()
    return _redis_cache