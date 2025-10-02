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
    
    def track_metrics(self, tracker, func, model_name=None, user_id=None, user_context=None, prev_message_count=0):
        """Track metrics with LaunchDarkly including cost tracking"""
        if not tracker:
            return func()

        try:
            # Use tracker's built-in duration tracking
            result = tracker.track_duration_of(func)
            tracker.track_success()

            # For LangGraph agents, usage_metadata is included on all messages that used AI
            total_input_tokens = 0
            total_output_tokens = 0
            total_tokens = 0

            if isinstance(result, dict) and "messages" in result:
                # Only look at messages that were added during this function call
                new_messages = result['messages'][prev_message_count:]
                for message in new_messages:
                    # Check for usage_metadata directly on the message
                    if hasattr(message, "usage_metadata") and message.usage_metadata:
                        usage_data = message.usage_metadata
                        total_input_tokens += usage_data.get("input_tokens", 0)
                        total_output_tokens += usage_data.get("output_tokens", 0)
                        total_tokens += usage_data.get("total_tokens", 0)

            # Track token usage if found
            if total_tokens > 0:
                token_usage = TokenUsage(
                    input=total_input_tokens,
                    output=total_output_tokens,
                    total=total_tokens
                )
                tracker.track_tokens(token_usage)
                log_student(f"TOKEN TRACKING: {total_tokens} tokens ({total_input_tokens} in, {total_output_tokens} out)")

                # Calculate and track cost using the token counts
                if model_name and user_id:
                    cost = calculate_cost(model_name, total_input_tokens, total_output_tokens)
                    if cost > 0:
                        # Build context for LaunchDarkly
                        context_builder = Context.builder(user_id).kind('user')
                        if user_context:
                            for key, value in user_context.items():
                                context_builder.set(key, value)
                        ld_context = context_builder.build()

                        # Track cost as custom event with metric value
                        self.ld_client.track("ai_cost_per_request", ld_context, None, cost)
                        log_student(f"COST TRACKING: ${cost:.6f} for {model_name} ({total_tokens} tokens)")
                        self.ld_client.flush()

            self.ld_client.flush()
            return result

        except Exception:
            tracker.track_error()
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

    async def track_metrics_async(self, tracker, async_func, model_name=None, user_id=None, user_context=None, prev_message_count=0):
        """Async variant of metrics tracking with cost calculation"""
        if not tracker:
            return await async_func()

        start_time = time.time()
        try:
            result = await async_func()

            # Track duration manually for async
            duration_ms = int((time.time() - start_time) * 1000)
            if hasattr(tracker, 'track_duration'):
                tracker.track_duration(duration_ms)

            if hasattr(tracker, 'track_success'):
                tracker.track_success()

            # For LangGraph agents, usage_metadata is included on all messages that used AI
            total_input_tokens = 0
            total_output_tokens = 0
            total_tokens = 0

            if isinstance(result, dict) and "messages" in result:
                # Only look at messages that were added during this function call
                new_messages = result['messages'][prev_message_count:]
                for message in new_messages:
                    # Check for usage_metadata directly on the message
                    if hasattr(message, "usage_metadata") and message.usage_metadata:
                        usage_data = message.usage_metadata
                        total_input_tokens += usage_data.get("input_tokens", 0)
                        total_output_tokens += usage_data.get("output_tokens", 0)
                        total_tokens += usage_data.get("total_tokens", 0)

            # Track tokens and cost
            if total_tokens > 0:
                token_usage = TokenUsage(
                    input=total_input_tokens,
                    output=total_output_tokens,
                    total=total_tokens
                )
                tracker.track_tokens(token_usage)
                log_student(f"TOKEN TRACKING (async): {total_tokens} tokens ({total_input_tokens} in, {total_output_tokens} out)")

                # Calculate and track cost using the token counts
                if model_name and user_id:
                    cost = calculate_cost(model_name, total_input_tokens, total_output_tokens)
                    if cost > 0:
                        context_builder = Context.builder(user_id).kind('user')
                        if user_context:
                            for key, value in user_context.items():
                                context_builder.set(key, value)
                        ld_context = context_builder.build()

                        self.ld_client.track("ai_cost_per_request", ld_context, None, cost)
                        log_student(f"COST TRACKING (async): ${cost:.6f} for {model_name}")
                        self.ld_client.flush()

            return result
        except Exception:
            if hasattr(tracker, 'track_error'):
                tracker.track_error()
            raise

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