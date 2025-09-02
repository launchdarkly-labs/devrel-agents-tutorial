import os
from typing import Dict, List, Optional
from dataclasses import dataclass
import ldclient
from ldclient import Context
from ldai.client import LDAIClient
from ldai.client import LDAIAgentConfig, LDAIAgentDefaults, ModelConfig
from ldai.tracker import LDAIConfigTracker

@dataclass
class AgentConfig:
    variation_key: str
    model: str
    instructions: str
    allowed_tools: List[str]
    max_tool_calls: int
    max_cost: float
    temperature: float = 0.0  # Model temperature
    workflow_type: str = "sequential"  # sequential, parallel, conditional
    tracker: Optional[LDAIConfigTracker] = None  # AI metrics tracker

class ConfigManager:
    def __init__(self):
        self.ld_client = None
        self.ai_client = None
        self.advanced_metrics = None
        self.initialization_error = None
        
        sdk_key = os.getenv('LD_SDK_KEY')
        if not sdk_key:
            print("⚠️ LD_SDK_KEY environment variable not set - LaunchDarkly features disabled")
            return
        
        # Try to initialize LaunchDarkly client with retries
        self._initialize_launchdarkly(sdk_key)
        
        # Initialize advanced metrics tracker regardless of LD status
        try:
            from ai_metrics.metrics_tracker import AdvancedMetricsTracker
            self.advanced_metrics = AdvancedMetricsTracker(config_manager=self)
            print("✅ Advanced metrics tracker initialized")
        except Exception as e:
            print(f"⚠️ Advanced metrics tracker initialization failed: {e}")
            self.advanced_metrics = None
    
    def _initialize_launchdarkly(self, sdk_key: str):
        """Initialize LaunchDarkly client with retry logic"""
        import time
        
        # Try multiple times with different configurations
        for attempt in range(3):
            try:
                print(f"🔄 Attempting to initialize LaunchDarkly client (attempt {attempt + 1}/3)")
                
                # Configure LaunchDarkly with different settings for each attempt
                if attempt == 0:
                    # First attempt: Standard configuration
                    ldclient.set_config(ldclient.Config(sdk_key, initial_reconnect_delay=1))
                elif attempt == 1:
                    # Second attempt: With offline mode as fallback
                    ldclient.set_config(ldclient.Config(sdk_key, initial_reconnect_delay=2, offline=False))
                else:
                    # Third attempt: With shorter timeouts
                    ldclient.set_config(ldclient.Config(sdk_key, initial_reconnect_delay=1, timeout=5))
                
                self.ld_client = ldclient.get()
                
                # Wait for client initialization with timeout
                max_wait = 10  # 10 seconds max
                wait_interval = 0.1  # Check every 100ms
                waited = 0
                
                while not self.ld_client.is_initialized() and waited < max_wait:
                    time.sleep(wait_interval)
                    waited += wait_interval
                
                if self.ld_client.is_initialized():
                    print("✅ LaunchDarkly client initialized successfully")
                    # Give the client a moment to fully stabilize
                    time.sleep(0.5)
                    
                    # Initialize LaunchDarkly AI client
                    try:
                        self.ai_client = LDAIClient(self.ld_client)
                        print("✅ LaunchDarkly AI client created")
                        return  # Success!
                    except Exception as e:
                        print(f"⚠️ LaunchDarkly AI client creation failed: {e}")
                        self.initialization_error = f"AI client creation failed: {e}"
                else:
                    print(f"⚠️ LaunchDarkly client not initialized after {max_wait}s")
                    self.initialization_error = f"Client not initialized after {max_wait}s"
                    
            except Exception as e:
                print(f"⚠️ LaunchDarkly client initialization attempt {attempt + 1} failed: {e}")
                self.initialization_error = str(e)
                if attempt < 2:  # Don't sleep on the last attempt
                    time.sleep(2 ** attempt)  # Exponential backoff
        
        # If we get here, all attempts failed
        print("❌ All LaunchDarkly initialization attempts failed - using fallback mode")
        self.ld_client = None
        self.ai_client = None
    
    def flush_metrics(self):
        """Flush LaunchDarkly metrics immediately"""
        if not self.ld_client:
            print("⚠️ LaunchDarkly client not available, cannot flush metrics")
            return
            
        try:
            if hasattr(self.ld_client, 'flush'):
                self.ld_client.flush()
                print("✅ METRICS: Flushed to LaunchDarkly")
            else:
                print("⚠️ METRICS: No flush method available")
        except Exception as e:
            print(f"❌ METRICS FLUSH ERROR: {e}")
    
    def close(self):
        """Close LaunchDarkly client and flush metrics"""
        if not self.ld_client:
            return
            
        try:
            self.flush_metrics()
            if hasattr(self.ld_client, 'close'):
                self.ld_client.close()
        except Exception as e:
            print(f"❌ CLOSE ERROR: {e}")
    
    def clear_cache(self):
        """Clear LaunchDarkly SDK cache"""
        if not self.ld_client or not self.ld_client.is_initialized():
            print("⚠️ LaunchDarkly client not initialized, cannot clear cache")
            return
            
        try:
            # Force LaunchDarkly to refresh from server
            self.ld_client.flush()
            print("✅ LaunchDarkly cache cleared")
        except Exception as e:
            print(f"⚠️ Cache clear failed: {e}")
    
    async def get_agent_with_tracker(self, user_id: str, config_key: str = None, user_context: dict = None):
        """Get LDAI Agent (Agent mode) from LaunchDarkly with tracker for metrics"""
        if not self.ai_client:
            print("⚠️ LaunchDarkly AI client not available, using fallback configuration")
            # Return fallback configuration
            return self._get_fallback_agent(config_key or 'support-agent')
        
        # Build user context with explicit kind 'user' to match LD targeting
        context_builder = Context.builder(user_id).kind('user')
        
        if user_context:
            # Add geographic targeting attributes
            if 'country' in user_context:
                context_builder.set('country', user_context['country'])
            if 'plan' in user_context:
                context_builder.set('plan', user_context['plan'])
            if 'region' in user_context:
                context_builder.set('region', user_context['region'])
            
            print(f"🌍 USER CONTEXT: {user_id} from {user_context.get('country', 'unknown')} on {user_context.get('plan', 'unknown')} plan")
        
        ld_user_context = context_builder.build()
        
        # Get Agent key from parameter or environment variable
        if config_key:
            agent_key = config_key
        else:
            agent_key = os.getenv('LAUNCHDARKLY_AI_CONFIG_KEY', 'support-agent')
        
        # Get Agent with tracker using the AI SDK (Agent mode)
        try:
            # Provide reasonable Agent defaults as fallback
            defaults = LDAIAgentDefaults(
                enabled=True,
                model=ModelConfig("claude-3-7-sonnet-latest"),
                instructions="You are a helpful AI assistant that can search documentation."
            )
            agent_config = LDAIAgentConfig(key=agent_key, default_value=defaults)
            
            print(f"🔍 DEBUG: Requesting LDAI agent '{agent_key}' for user {user_id}")
            
            agent = self.ai_client.agent(agent_config, ld_user_context)
            tracker = getattr(agent, "tracker", None)
            
            if agent and getattr(agent, 'enabled', False):
                print(f"✅ LDAI AGENT LOADED: {agent_key} for user {user_id}")
                return agent, tracker
            else:
                print(f"⚠️  LDAI AGENT NOT AVAILABLE: {agent_key} for user {user_id}")
                # Return fallback configuration
                return self._get_fallback_agent(agent_key)
                
        except Exception as e:
            print(f"⚠️  LDAI AGENT ERROR: Agent '{agent_key}' not available: {e}")
            # Return fallback configuration
            return self._get_fallback_agent(agent_key)
    
    def _get_fallback_agent(self, agent_key: str):
        """Get fallback agent configuration when LaunchDarkly is not available"""
        print(f"🔄 Using fallback configuration for agent: {agent_key}")
        
        # Default configurations based on agent type
        configs = {
            "supervisor-agent": {
                "instructions": "You are a helpful AI assistant that coordinates between different specialized agents.",
                "model": "claude-3-7-sonnet-latest",
                "allowed_tools": []
            },
            "support-agent": {
                "instructions": "You are a helpful AI assistant that can search documentation and answer questions.",
                "model": "claude-3-7-sonnet-latest",
                "allowed_tools": ["search_v2", "reranking", "semantic_scholar", "arxiv_search"]
            },
            "security-agent": {
                "instructions": "You are a security-focused AI assistant that reviews content for safety.",
                "model": "claude-3-7-sonnet-latest",
                "allowed_tools": []
            }
        }
        
        config = configs.get(agent_key, configs["support-agent"])
        
        # Create a mock agent object
        class MockAgent:
            def __init__(self, instructions, model):
                self.instructions = instructions
                self.model = type('Model', (), {'name': model})()
                self.enabled = True
        
        mock_agent = MockAgent(config["instructions"], config["model"])
        return mock_agent, None  # No tracker for fallback
    
    async def get_agents_with_trackers(self, user_id: str, agent_keys: List[str], user_context: dict = None):
        """Batch fetch multiple LDAI agents with trackers using LDAIClient.agents (matches docs)."""
        if not self.ai_client:
            print("⚠️ LaunchDarkly AI client not available, using fallback configurations")
            # Return fallback configurations
            parsed: Dict[str, AgentConfig] = {}
            for key in agent_keys:
                mock_agent, tracker = self._get_fallback_agent(key)
                cfg = self._parse_agent_object(mock_agent, key)
                cfg.tracker = tracker
                parsed[key] = cfg
            return parsed
        
        # Build LD context
        context_builder = Context.builder(user_id).kind('user')
        if user_context:
            if 'country' in user_context:
                context_builder.set('country', user_context['country'])
            if 'plan' in user_context:
                context_builder.set('plan', user_context['plan'])
            if 'region' in user_context:
                context_builder.set('region', user_context['region'])
        ld_user_context = context_builder.build()

        # Prepare agent configs with reasonable defaults
        agent_configs = []
        for key in agent_keys:
            defaults = LDAIAgentDefaults(
                enabled=True,
                model=ModelConfig("claude-3-7-sonnet-latest"),
                instructions="You are a helpful AI assistant that can search documentation."
            )
            agent_configs.append(LDAIAgentConfig(key=key, default_value=defaults))

        # Fetch in one call
        try:
            result = self.ai_client.agents(agent_configs, ld_user_context)

            # Map to parsed AgentConfig with tracker
            parsed: Dict[str, AgentConfig] = {}
            for key, agent_obj in result.items():
                cfg = self._parse_agent_object(agent_obj, key)
                cfg.tracker = getattr(agent_obj, 'tracker', None)
                parsed[key] = cfg
            return parsed
        except Exception as e:
            print(f"⚠️ Batch agent fetch failed: {e}, using fallback configurations")
            # Return fallback configurations
            parsed: Dict[str, AgentConfig] = {}
            for key in agent_keys:
                mock_agent, tracker = self._get_fallback_agent(key)
                cfg = self._parse_agent_object(mock_agent, key)
                cfg.tracker = tracker
                parsed[key] = cfg
            return parsed
        
    async def get_config(self, user_id: str, config_key: str = None, user_context: dict = None) -> AgentConfig:
        """Get agent configuration with AI metrics tracking (Agent mode)."""
        # Get LDAI Agent with tracker - NO FALLBACK
        agent, tracker = await self.get_agent_with_tracker(user_id, config_key, user_context)
        config = self._parse_agent_object(agent, config_key or 'support-agent')
        config.tracker = tracker
        return config
    
    def _parse_agent_object(self, ai_agent, agent_key: str) -> AgentConfig:
        """Parse LDAIAgent object from LaunchDarkly AI SDK (Agent mode)"""
        model = getattr(getattr(ai_agent, 'model', None), 'name', None) or "claude-3-7-sonnet-latest"
        
        # For now, use hardcoded values since the AI SDK handles most configuration
        # In a real implementation, you'd extract these from custom parameters
        variation_key = "main"  # Default variation (tracker holds actual variation)
        instructions = getattr(ai_agent, 'instructions', None) or "You are a helpful AI assistant that can search documentation."
        allowed_tools = ["search_v2", "reranking", "semantic_scholar", "arxiv_search"]  # Default tools
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
        """Wrapper for tracking operations with LaunchDarkly metrics."""
        if tracker:
            try:
                # Use the comprehensive tracking function that includes TTFT
                from ai_metrics.metrics_tracker import track_langchain_metrics
                return track_langchain_metrics(tracker, func)
            except Exception as e:
                print(f"⚠️ Metrics tracking failed: {e}")
                return func()
        else:
            # No tracker available, just execute function
            return func()
    
    def get_advanced_metrics(self):
        """Get the advanced metrics tracker instance"""
        return self.advanced_metrics