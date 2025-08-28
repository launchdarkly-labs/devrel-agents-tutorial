import os
from typing import Dict, List
from dataclasses import dataclass
import ldclient
from ldclient import Context
from utils.redis_cache import get_redis_cache

@dataclass
class AgentConfig:
    variation_key: str
    model: str
    instructions: str
    allowed_tools: List[str]
    max_tool_calls: int
    max_cost: float
    workflow_type: str = "sequential"  # sequential, parallel, conditional

class ConfigManager:
    def __init__(self):
        sdk_key = os.getenv('LD_SDK_KEY')
        if not sdk_key:
            raise ValueError("LD_SDK_KEY environment variable is required")
        ldclient.set_config(ldclient.Config(sdk_key))
        self.ld_client = ldclient.get()
        self.cache = get_redis_cache()
        
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
        
    async def get_config(self, user_id: str, config_key: str = None) -> AgentConfig:
        user_context = Context.builder(user_id).build()
        
        # Get AI Config key from parameter or environment variable
        if config_key:
            ai_config_key = config_key
        else:
            ai_config_key = os.getenv('LAUNCHDARKLY_AI_CONFIG_KEY', 'support-agent')
        
        # Check Redis cache first
        cached_config = self.cache.get_ld_config(user_id, ai_config_key)
        if cached_config:
            return self._parse_config(cached_config, ai_config_key)
        
        # Get AI Config from LaunchDarkly - no defaults, must be configured
        ai_config = self.ld_client.variation(
            ai_config_key,
            user_context,
            None  # No default - LaunchDarkly must provide configuration
        )
        
        
        # Cache the result
        if ai_config:
            self.cache.cache_ld_config(user_id, ai_config_key, ai_config)
        
        if ai_config is None:
            raise ValueError(f"LaunchDarkly AI Config '{ai_config_key}' is not configured. Configuration is required.")
        
        return self._parse_config(ai_config, ai_config_key)
    
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
        
        # Extract tools from LaunchDarkly AI Config structure
        allowed_tools = []
        if "model" in ai_config and "parameters" in ai_config["model"] and "tools" in ai_config["model"]["parameters"]:
            tools_config = ai_config["model"]["parameters"]["tools"]
            print(f"DEBUG: Raw LaunchDarkly tools config: {tools_config}")
            print(f"DEBUG: Tools config type: {type(tools_config)}")
            
            # Handle both string array and object array formats
            if isinstance(tools_config, list) and tools_config:
                if isinstance(tools_config[0], str):
                    # Simple string array: ["search_v2", "reranking", "arxiv_search"]
                    allowed_tools = tools_config
                    print(f"DEBUG: Using string array format: {allowed_tools}")
                elif isinstance(tools_config[0], dict) and "name" in tools_config[0]:
                    # Object array: [{"name": "search_v2"}, {"name": "reranking"}]
                    allowed_tools = [tool["name"] for tool in tools_config]
                    print(f"DEBUG: Using object array format: {allowed_tools}")
            
            print(f"DEBUG: Final allowed_tools: {allowed_tools}")
        
        # Get instructions from LaunchDarkly AI Config
        instructions = ai_config.get("instructions", "You are a helpful AI assistant.")
        
        # Get custom parameters from model.custom
        custom_params = ai_config.get("model", {}).get("custom", {})
        
        # Get configuration parameters with sensible defaults - NO REQUIRED FIELDS
        # This allows complete flexibility in LaunchDarkly AI Config structure
        max_tool_calls = custom_params.get("max_tool_calls", 8)  # Default: 8 tool calls
        max_cost = custom_params.get("max_cost", 1.0)            # Default: $1.00 max cost
        workflow_type = custom_params.get("workflow_type", "sequential")  # Default: sequential
        
        return AgentConfig(
            variation_key=variation_key,
            model=model,
            instructions=instructions,
            allowed_tools=allowed_tools,
            max_tool_calls=max_tool_calls,
            max_cost=max_cost,
            workflow_type=workflow_type
        )