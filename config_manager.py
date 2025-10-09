#!/usr/bin/env python3
"""
Simplified ConfigManager for LaunchDarkly AI Agent integration
"""
import os
import time
import ldclient
from ldclient import Context
from ldai.client import LDAIClient, LDAIAgentConfig, LDAIAgentDefaults, ModelConfig
from ldai.tracker import TokenUsage, FeedbackKind
from dotenv import load_dotenv
from utils.logger import log_student, log_debug
from utils.cost_calculator import calculate_cost

load_dotenv()

def map_provider_to_langchain(provider_name):
    """Map LaunchDarkly provider names to LangChain provider names."""
    provider_mapping = {
        'gemini': 'google_genai',
        'anthropic': 'anthropic', 
        'openai': 'openai',
        'mistral': 'mistralai'
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
        log_debug(f"CONFIG MANAGER: Getting config for user_id={user_id}, config_key={config_key}")
        log_debug(f"CONFIG MANAGER: User context: {user_context}")
        
        context_builder = Context.builder(user_id).kind('user')
        
        if user_context:
            if 'country' in user_context:
                context_builder.set('country', user_context['country'])
                log_debug(f"CONFIG MANAGER: Set country={user_context['country']}")
            if 'plan' in user_context:
                context_builder.set('plan', user_context['plan'])
                log_debug(f"CONFIG MANAGER: Set plan={user_context['plan']}")
            if 'region' in user_context:
                context_builder.set('region', user_context['region'])
                log_debug(f"CONFIG MANAGER: Set region={user_context['region']}")
        
        ld_user_context = context_builder.build()
        log_debug(f"CONFIG MANAGER: Built LaunchDarkly context: {ld_user_context}")
        
        ai_config_key = config_key or os.getenv('LAUNCHDARKLY_AI_CONFIG_KEY', 'support-agent')
        log_debug(f"CONFIG MANAGER: Using AI config key: {ai_config_key}")
        
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
            log_debug(f"CONFIG MANAGER: Got result from LaunchDarkly")
            
            # Debug the actual configuration received (basic info only)
            try:
                config_dict = result.to_dict()
                log_debug(f"CONFIG MANAGER: Model: {config_dict.get('model', {}).get('name', 'unknown')}")
                if hasattr(result, 'tracker') and hasattr(result.tracker, '_variation_key'):
                    log_debug(f"CONFIG MANAGER: Variation: {result.tracker._variation_key}")
            except Exception as debug_e:
                log_debug(f"CONFIG MANAGER: Could not debug result: {debug_e}")
            
            return result
        except Exception as e:
            log_student(f"CONFIG MANAGER ERROR: {e}")
            import traceback
            log_debug(f"CONFIG MANAGER ERROR TRACEBACK: {traceback.format_exc()}")
            raise
    

    def clear_cache(self):
        """Clear LaunchDarkly SDK cache"""
        self.ld_client.flush()

    def flush_metrics(self):
        """Flush metrics to LaunchDarkly"""
        self.ld_client.flush()

    def track_feedback(self, tracker, thumbs_up: bool):
        """Track user feedback with LaunchDarkly"""
        if not tracker:
            return False

        try:
            # Use LaunchDarkly's feedback tracking
            feedback_dict = {
                "kind": FeedbackKind.Positive if thumbs_up else FeedbackKind.Negative
            }
            tracker.track_feedback(feedback_dict)
            log_student(f"FEEDBACK TRACKED: {'👍 Positive' if thumbs_up else '👎 Negative'}")
            self.ld_client.flush()
            return True
        except Exception as e:
            log_debug(f"FEEDBACK TRACKING ERROR: {e}")
            return False

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