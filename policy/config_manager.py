import os
from typing import Dict, List, Optional
from dataclasses import dataclass
import ldclient
from ldclient import Context
from ldai.client import LDAIClient
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
        sdk_key = os.getenv('LD_SDK_KEY')
        if not sdk_key:
            raise ValueError("LD_SDK_KEY environment variable is required")
        
        # Configure LaunchDarkly with startup wait time
        ldclient.set_config(ldclient.Config(sdk_key, initial_reconnect_delay=1))
        self.ld_client = ldclient.get()
        
        # Wait for client initialization
        if self.ld_client.is_initialized():
            print("✅ LaunchDarkly client initialized successfully")
        else:
            print("⚠️ LaunchDarkly client not initialized - configs may not be available")
        
        # Initialize LaunchDarkly AI client
        self.ai_client = LDAIClient(self.ld_client)
        
    def clear_cache(self):
        """Clear LaunchDarkly SDK cache"""
        try:
            # Force LaunchDarkly to refresh from server
            self.ld_client.flush()
            
            # Also try to recreate the client entirely
            sdk_key = os.getenv('LD_SDK_KEY')
            ldclient.set_config(ldclient.Config(sdk_key))
            self.ld_client = ldclient.get()
            
            print("DEBUG: LaunchDarkly cache flushed and client recreated")
        except Exception as e:
            print(f"DEBUG: Cache flush failed: {e}")
            
    async def get_ai_config_with_tracker(self, user_id: str, config_key: str = None, user_context: dict = None) -> tuple[dict, LDAIConfigTracker]:
        """Get AI Config from LaunchDarkly with tracker for metrics"""
        # Build user context with optional geographic and other attributes
        context_builder = Context.builder(user_id)
        
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
        
        # Get AI Config key from parameter or environment variable
        if config_key:
            ai_config_key = config_key
        else:
            ai_config_key = os.getenv('LAUNCHDARKLY_AI_CONFIG_KEY', 'support-agent')
        
        # Get AI Config with tracker using the AI SDK
        try:
            # AI SDK requires a proper AIConfig as fallback - use disabled config to indicate failure
            from ldai.client import AIConfig
            fallback_value = AIConfig(enabled=False)
            
            print(f"🔍 DEBUG: Requesting AI config '{ai_config_key}' for user {user_id}")
            print(f"🔍 DEBUG: LaunchDarkly client initialized: {self.ld_client.is_initialized()}")
            
            config, tracker = self.ai_client.config(ai_config_key, ld_user_context, fallback_value)
            
            print(f"🔍 DEBUG: Config type: {type(config)}")
            print(f"🔍 DEBUG: Config enabled: {getattr(config, 'enabled', 'no enabled attr')}")
            print(f"🔍 DEBUG: Config: {config}")
            
            if config and hasattr(config, 'enabled') and config.enabled:
                print(f"✅ AI CONFIG LOADED: {ai_config_key} for user {user_id}")
                return config, tracker
            else:
                print(f"⚠️  AI CONFIG NOT AVAILABLE: {ai_config_key} for user {user_id} - using fallback")
                raise ValueError(f"LaunchDarkly AI Config '{ai_config_key}' is not configured or disabled")
                
        except Exception as e:
            print(f"⚠️  AI CONFIG FALLBACK: AI config '{ai_config_key}' not available: {e}")
            raise ValueError(f"Failed to load LaunchDarkly AI Config '{ai_config_key}': {e}")
        
    async def get_config(self, user_id: str, config_key: str = None, user_context: dict = None) -> AgentConfig:
        """Get agent configuration with AI metrics tracking - LaunchDarkly required"""
        # Get AI Config with tracker - NO FALLBACK
        ai_config, tracker = await self.get_ai_config_with_tracker(user_id, config_key, user_context)
        config = self._parse_ai_config_object(ai_config, config_key or 'support-agent')
        config.tracker = tracker
        return config
    
    def _parse_ai_config_object(self, ai_config, ai_config_key: str) -> AgentConfig:
        """Parse AIConfig object from LaunchDarkly AI SDK"""
        print(f"🔍 DEBUG: Parsing AIConfig object: {ai_config}")
        print(f"🔍 DEBUG: Model: {ai_config.model}")
        print(f"🔍 DEBUG: Model name: {ai_config.model.name}")
        
        # Extract model name from AIConfig object
        model = ai_config.model.name
        
        # For now, use hardcoded values since the AI SDK handles most configuration
        # In a real implementation, you'd extract these from custom parameters
        variation_key = "main"  # Default variation
        instructions = "You are a helpful AI assistant that can search documentation."
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
                # Use the tracker's track_duration_of method if available
                return tracker.track_duration_of(func)
            except Exception as e:
                print(f"⚠️ Metrics tracking failed: {e}")
                return func()
        else:
            # No tracker available, just execute function
            return func()
    
    def _parse_config(self, ai_config: dict, ai_config_key: str) -> AgentConfig:
        """Parse AI config into AgentConfig object"""
        # Extract variation key from AI Config metadata
        variation_key = ai_config.get("_ldMeta", {}).get("variationKey", "unknown")
        if not variation_key or variation_key == "unknown":
            variation_key = "baseline"
        
        # Extract model name from LaunchDarkly AI Config structure - REQUIRED by LaunchDarkly AI Config spec
        model = ai_config.get("model")
        if not model:
            raise ValueError("Model configuration is required in LaunchDarkly AI Config")
        
        if isinstance(model, dict) and "name" in model:
            model = model["name"]
        elif isinstance(model, dict):
            raise ValueError("Model configuration must contain 'name' field when using dict format")
        
        # Map LaunchDarkly model names to correct Anthropic model IDs
        model_mapping = {
            "claude-3-5-sonnet-20241022": "claude-3-5-sonnet-20241022",
            "claude-3-5-sonnet": "claude-3-5-sonnet-20241022"
        }
        
        if model in model_mapping:
            model = model_mapping[model]
        
        # Extract tools from LaunchDarkly AI Config structure - handle multiple possible formats
        allowed_tools = []
        
        # Try multiple possible tool locations in LaunchDarkly AI Config
        tools_config = None
        
        # Format 1: model.parameters.tools
        if "model" in ai_config and "parameters" in ai_config["model"] and "tools" in ai_config["model"]["parameters"]:
            tools_config = ai_config["model"]["parameters"]["tools"]
            print(f"DEBUG: Found tools in model.parameters.tools: {tools_config}")
            
        # Format 2: Direct tools array
        elif "tools" in ai_config:
            tools_config = ai_config["tools"]
            print(f"DEBUG: Found tools directly: {tools_config}")
            
        # Format 3: internal_tools + other_tools (LaunchDarkly UI format)
        elif "internal_tools" in ai_config or "other_tools" in ai_config:
            tools_config = []
            if "internal_tools" in ai_config:
                internal = ai_config["internal_tools"]
                if isinstance(internal, list):
                    tools_config.extend(internal)
            if "other_tools" in ai_config:
                other = ai_config["other_tools"] 
                if isinstance(other, list):
                    tools_config.extend(other)
            print(f"DEBUG: Found tools in internal_tools/other_tools: {tools_config}")
        
        if tools_config:
            print(f"DEBUG: Raw LaunchDarkly tools config: {tools_config}")
            print(f"DEBUG: Tools config type: {type(tools_config)}")
            
            # Handle multiple formats
            if isinstance(tools_config, list) and tools_config:
                for tool in tools_config:
                    if isinstance(tool, str):
                        # Simple string: "search_v2"
                        allowed_tools.append(tool)
                    elif isinstance(tool, dict) and "name" in tool:
                        # Object with name: {"name": "search_v2"}
                        allowed_tools.append(tool["name"])
                    elif isinstance(tool, dict):
                        # Handle other dict formats - look for common tool name fields
                        tool_name = tool.get("tool_name") or tool.get("id") or str(tool)
                        allowed_tools.append(tool_name)
                    else:
                        # Handle any other type by converting to string
                        allowed_tools.append(str(tool))
                        
            print(f"DEBUG: Final allowed_tools: {allowed_tools}")
        else:
            print("DEBUG: No tools configuration found in LaunchDarkly AI Config")
        
        # Get instructions from LaunchDarkly AI Config
        instructions = ai_config.get("instructions", "You are a helpful AI assistant.")
        
        # Get custom parameters from model.custom
        custom_params = ai_config.get("model", {}).get("custom", {})
        
        # Get configuration parameters with sensible defaults - NO REQUIRED FIELDS
        # This allows complete flexibility in LaunchDarkly AI Config structure
        max_tool_calls = custom_params.get("max_tool_calls", 8)  # Default: 8 tool calls
        max_cost = custom_params.get("max_cost", 1.0)            # Default: $1.00 max cost
        temperature = custom_params.get("temperature", 0.0)      # Default: 0.0 temperature
        workflow_type = custom_params.get("workflow_type", "sequential")  # Default: sequential
        
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
                # Use the tracker's track_duration_of method if available
                return tracker.track_duration_of(func)
            except Exception as e:
                print(f"⚠️ Metrics tracking failed: {e}")
                return func()
        else:
            # No tracker available, just execute function
            return func()