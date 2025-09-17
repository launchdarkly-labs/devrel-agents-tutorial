#!/usr/bin/env python3
"""
Simplified ConfigManager for LaunchDarkly AI Agent integration
"""
import os
import time
import ldclient
from ldclient import Context
from ldai.client import LDAIClient, LDAIAgentConfig, LDAIAgentDefaults, ModelConfig
from dotenv import load_dotenv
from utils.logger import log_student, log_debug

load_dotenv()

def map_provider_to_langchain(provider_name):
    """Map LaunchDarkly provider names to LangChain provider names."""
    provider_mapping = {
        'gemini': 'google_genai',
        'anthropic': 'anthropic', 
        'openai': 'openai'
    }
    lower_provider = provider_name.lower()
    return provider_mapping.get(lower_provider, lower_provider)

class FixedConfigManager:
    def __init__(self):
        """Initialize LaunchDarkly client and AI client"""
        self.sdk_key = os.getenv('LD_SDK_KEY')
        if not self.sdk_key:
            raise ValueError("LD_SDK_KEY environment variable is required")
        
        self._initialize_launchdarkly_client()
        self._initialize_ai_client()
    
    def _initialize_launchdarkly_client(self):
        """Initialize LaunchDarkly client"""
        config = ldclient.Config(self.sdk_key)
        ldclient.set_config(config)
        self.ld_client = ldclient.get()
        
        max_wait = 10
        wait_time = 0
        while not self.ld_client.is_initialized() and wait_time < max_wait:
            time.sleep(0.5)
            wait_time += 0.5
        
        if not self.ld_client.is_initialized():
            raise RuntimeError("LaunchDarkly client initialization failed")
    
    def _initialize_ai_client(self):
        """Initialize AI client"""
        self.ai_client = LDAIClient(self.ld_client)
    
    async def get_config(self, user_id: str, config_key: str = None, user_context: dict = None):
        """Get LaunchDarkly AI Config object directly - no wrapper"""
        # Removed verbose logging - use DEBUG mode if needed
        
        context_builder = Context.builder(user_id).kind('user')
        
        if user_context:
            if 'country' in user_context:
                context_builder.set('country', user_context['country'])
            if 'plan' in user_context:
                context_builder.set('plan', user_context['plan'])
            if 'region' in user_context:
                context_builder.set('region', user_context['region'])
        
        ld_user_context = context_builder.build()
        
        ai_config_key = config_key or os.getenv('LAUNCHDARKLY_AI_CONFIG_KEY', 'support-agent')
        
        agent_config = LDAIAgentConfig(
            key=ai_config_key,
            default_value=LDAIAgentDefaults(
                enabled=True,
                model=ModelConfig(name="claude-3-haiku-20240307"),
                instructions="You are a helpful assistant."
            )
        )
        
        try:
            # Return the AI Config object directly
            result = self.ai_client.agent(agent_config, ld_user_context)
            return result
        except Exception as e:
            log_student(f"🔧 CONFIG MANAGER ERROR: {e}")
            import traceback
            log_debug(f"🔧 CONFIG MANAGER ERROR TRACEBACK: {traceback.format_exc()}")
            raise
    
    def track_metrics(self, tracker, func):
        """Track metrics with LaunchDarkly"""
        if not tracker:
            return func()
        
        try:
            from ai_metrics.metrics_tracker import track_langgraph_metrics
            result = track_langgraph_metrics(tracker, func)
            
            # track_langgraph_metrics already handles success and token tracking
            self.ld_client.flush()
            return result
            
        except Exception:
            # Track error and fallback
            try:
                tracker.track_error()
                self.ld_client.flush()
            except:
                pass
            return func()
    
    def clear_cache(self):
        """Clear LaunchDarkly SDK cache"""
        self.ld_client.flush()
    
    def flush_metrics(self):
        """Flush metrics to LaunchDarkly"""
        self.ld_client.flush()
    
    def close(self):
        """Close LaunchDarkly client"""
        try:
            self.ld_client.flush()
        except:
            pass
        try:
            self.ld_client.close()
        except:
            pass