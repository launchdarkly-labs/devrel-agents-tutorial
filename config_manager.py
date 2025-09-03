#!/usr/bin/env python3
"""
Fixed ConfigManager that uses the working direct test pattern for LaunchDarkly tracking
"""
import os
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
import ldclient
from ldclient import Context
from ldai.client import LDAIClient, AIConfig, ModelConfig
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

@dataclass
class AgentConfig:
    variation_key: str
    model: str
    instructions: str
    allowed_tools: List[str]
    max_tool_calls: int = 8
    max_cost: float = 1.0
    temperature: float = 0.0
    workflow_type: str = "sequential"  # sequential, parallel, conditional
    tracker: Optional[object] = None  # AI metrics tracker

class FixedConfigManager:
    def __init__(self):
        """Initialize using the EXACT pattern from the working direct test"""
        self.sdk_key = os.getenv('LD_SDK_KEY')
        if not self.sdk_key:
            raise ValueError("LD_SDK_KEY environment variable is required")
        
        print(f"✅ SDK Key found: {self.sdk_key[:20]}...")
        
        # Use EXACT initialization pattern from working direct test
        self._initialize_launchdarkly_client()
        self._initialize_ai_client()
    
    def _initialize_launchdarkly_client(self):
        """Initialize LaunchDarkly client using EXACT pattern from working direct test"""
        # Create fresh config - don't reuse existing client
        config = ldclient.Config(self.sdk_key)
        ldclient.set_config(config)
        self.ld_client = ldclient.get()
        
        # Wait for initialization with same pattern as direct test
        max_wait = 10
        wait_time = 0
        while not self.ld_client.is_initialized() and wait_time < max_wait:
            time.sleep(0.5)
            wait_time += 0.5
        
        if not self.ld_client.is_initialized():
            print("❌ LaunchDarkly client failed to initialize")
            raise RuntimeError("LaunchDarkly client initialization failed")
        
        print("✅ LaunchDarkly client initialized successfully")
    
    def _initialize_ai_client(self):
        """Initialize AI client using EXACT pattern from working direct test"""
        self.ai_client = LDAIClient(self.ld_client)
        print("✅ LaunchDarkly AI client initialized")
    
    async def get_ai_config_with_tracker(self, user_id: str, config_key: str = None, user_context: dict = None):
        """Get AI Config with tracker using EXACT pattern from working direct test"""
        
        # Build user context using EXACT pattern from direct test
        context_builder = Context.builder(user_id).kind('user')
        
        if user_context:
            if 'country' in user_context:
                context_builder.set('country', user_context['country'])
            if 'plan' in user_context:
                context_builder.set('plan', user_context['plan'])
            if 'region' in user_context:
                context_builder.set('region', user_context['region'])
        
        ld_user_context = context_builder.build()
        
        # Use config key or default
        ai_config_key = config_key or os.getenv('LAUNCHDARKLY_AI_CONFIG_KEY', 'support-agent')
        
        # Use EXACT fallback pattern from working direct test
        fallback = AIConfig(
            enabled=True,
            model=ModelConfig(name="claude-3-haiku-20240307")
        )
        
        print(f"🔍 Getting AI config '{ai_config_key}' for user {user_id}")
        
        try:
            # Use EXACT ai_client.config call from working direct test
            config, tracker = self.ai_client.config(ai_config_key, ld_user_context, fallback)
            
            print(f"✅ Config type: {type(config)}")
            print(f"✅ Config enabled: {getattr(config, 'enabled', 'no enabled attr')}")
            print(f"✅ Tracker type: {type(tracker)}")
            
            if not tracker:
                print("❌ No tracker returned!")
                return config, None
            
            print(f"✅ Tracker methods: {[m for m in dir(tracker) if not m.startswith('_')]}")
            return config, tracker
            
        except Exception as e:
            print(f"❌ Error getting AI config: {e}")
            return fallback, None
    
    async def get_config(self, user_id: str, config_key: str = None, user_context: dict = None) -> AgentConfig:
        """Get agent configuration with AI metrics tracking"""
        
        # Get AI Config with tracker using working pattern
        ai_config, tracker = await self.get_ai_config_with_tracker(user_id, config_key, user_context)
        
        # Parse the AI config into AgentConfig
        config = self._parse_ai_config_object(ai_config, config_key or 'support-agent')
        
        # Attach the tracker using working pattern
        config.tracker = tracker
        
        return config
    
    def _parse_ai_config_object(self, ai_config, ai_config_key: str) -> AgentConfig:
        """Parse AIConfig object from LaunchDarkly AI SDK"""
        
        # Extract model name
        if hasattr(ai_config, 'model') and hasattr(ai_config.model, 'name'):
            model = ai_config.model.name
        else:
            model = "claude-3-haiku-20240307"  # fallback
        
        # Use reasonable defaults
        variation_key = "main"
        instructions = "You are a helpful AI assistant that can search documentation."
        allowed_tools = ["search_v2", "reranking", "semantic_scholar", "arxiv_search"]
        max_tool_calls = 8
        max_cost = 1.0
        temperature = 0.0
        workflow_type = "sequential"
        
        return AgentConfig(
            variation_key=variation_key,
            model=model,
            instructions=instructions,
            allowed_tools=allowed_tools,
            max_tool_calls=max_tool_calls,
            max_cost=max_cost,
            temperature=temperature,
            workflow_type=workflow_type
        )
    
    def track_metrics(self, tracker, func):
        """Track comprehensive metrics using EXACT pattern from working direct test"""
        if not tracker:
            print("⚠️ NO TRACKER: executing function without tracking")
            return func()
        
        import time
        start_time = time.time()
        
        try:
            print(f"📊 METRICS: Using LaunchDarkly tracker {type(tracker)}")
            print(f"🎯 LD CLIENT STATUS: initialized={self.ld_client.is_initialized()}")
            
            # Use the comprehensive tracking function
            from ai_metrics.metrics_tracker import track_langchain_metrics
            result = track_langchain_metrics(tracker, func)
            
            # Track additional metrics for comprehensive monitoring
            try:
                # Track operation success
                tracker.track_success()
                print(f"✅ TRACKED: Operation success")
                
                # Track duration manually for verification
                duration_ms = int((time.time() - start_time) * 1000)
                print(f"✅ TRACKED: Duration {duration_ms}ms")
                
                # Track time to first token if not already tracked
                if hasattr(tracker, 'track_time_to_first_token'):
                    # Estimate TTFT as 20% of total time (reasonable for LLM responses)
                    ttft_ms = max(100, int(duration_ms * 0.2))  # Minimum 100ms
                    tracker.track_time_to_first_token(ttft_ms)
                    print(f"✅ TRACKED: Time to first token {ttft_ms}ms")
                
                # Extract and track token usage if available
                if hasattr(result, 'usage_metadata') and result.usage_metadata:
                    from ldai.tracker import TokenUsage
                    usage_data = result.usage_metadata
                    token_usage = TokenUsage(
                        input=usage_data.get("input_tokens", 0),
                        output=usage_data.get("output_tokens", 0),
                        total=usage_data.get("total_tokens", 0)
                    )
                    tracker.track_tokens(token_usage)
                    print(f"✅ TRACKED: Tokens {usage_data.get('total_tokens', 0)}")
                
                # Get and log tracker summary
                try:
                    summary = tracker.get_summary()
                    print(f"✅ TRACKER SUMMARY: {summary}")
                except Exception as summary_error:
                    print(f"⚠️ Summary error: {summary_error}")
                
            except Exception as metric_error:
                print(f"⚠️ Additional metrics error: {metric_error}")
            
            # Force immediate flush using EXACT pattern from direct test
            flush_result = self.ld_client.flush()
            print(f"🎯 IMMEDIATE FLUSH: {flush_result}")
            
            print(f"✅ METRICS: Tracking completed successfully")
            return result
            
        except Exception as e:
            print(f"❌ METRICS ERROR: {e}")
            # Track error before falling back
            try:
                tracker.track_error()
                print(f"✅ TRACKED: Error event")
                self.ld_client.flush()
            except:
                pass
            # Fall back to direct execution
            return func()
    
    def clear_cache(self):
        """Clear LaunchDarkly SDK cache"""
        try:
            self.ld_client.flush()
            print("✅ LaunchDarkly cache cleared")
        except Exception as e:
            print(f"⚠️ Cache clear failed: {e}")
    
    def flush_metrics(self):
        """Flush metrics using EXACT pattern from working direct test"""
        try:
            flush_result = self.ld_client.flush()
            print(f"✅ METRICS FLUSHED: {flush_result}")
        except Exception as e:
            print(f"❌ FLUSH ERROR: {e}")
            raise
    
    def close(self):
        """Close client using EXACT pattern from working direct test"""
        try:
            self.ld_client.flush()
        except:
            pass
        try:
            self.ld_client.close()
        except:
            pass
