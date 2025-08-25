import os
from typing import Dict, List
from dataclasses import dataclass
import ldclient
from ldclient import Context

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
        
    async def get_config(self, user_id: str) -> AgentConfig:
        user_context = Context.builder(user_id).build()
        
        # Get AI Config key from environment variable
        ai_config_key = os.getenv('LAUNCHDARKLY_AI_CONFIG_KEY', 'support-agent')
        
        # Get AI Config from LaunchDarkly - no defaults, must be configured
        ai_config = self.ld_client.variation(
            ai_config_key,
            user_context,
            None  # No default - LaunchDarkly must provide configuration
        )
        
        if ai_config is None:
            raise ValueError(f"LaunchDarkly AI Config '{ai_config_key}' is not configured. Configuration is required.")
        
        # Extract variation key from AI Config metadata
        variation_key = ai_config.get("_ldMeta", {}).get("variationKey", "unknown")
        if not variation_key or variation_key == "unknown":
            variation_key = "baseline"
        
        # Extract model name from LaunchDarkly AI Config structure - required
        model = ai_config.get("model")
        if not model:
            raise ValueError("Model configuration is required in LaunchDarkly AI Config")
        
        if isinstance(model, dict) and "name" in model:
            model = model["name"]
        elif isinstance(model, dict):
            raise ValueError("Model configuration must contain 'name' field when using dict format")
        
        # Map LaunchDarkly model names to correct Anthropic model IDs
        model_mapping = {
            "claude-3-5-sonnet-20240620": "claude-3-5-sonnet-20241022", 
            "claude-3-5-sonnet-20241022": "claude-3-5-sonnet-20241022",
            "claude-3-5-sonnet": "claude-3-5-sonnet-20241022"
        }
        
        if model in model_mapping:
            model = model_mapping[model]
        
        
        # Extract tools from LaunchDarkly AI Config structure
        allowed_tools = []
        if "model" in ai_config and "parameters" in ai_config["model"] and "tools" in ai_config["model"]["parameters"]:
            allowed_tools = [tool["name"] for tool in ai_config["model"]["parameters"]["tools"]]
        
        # Validate all required configuration fields
        instructions = ai_config.get("instructions")
        if not instructions:
            raise ValueError("Instructions are required in LaunchDarkly AI Config")
        
        max_tool_calls = ai_config.get("max_tool_calls")
        if max_tool_calls is None:
            raise ValueError("max_tool_calls is required in LaunchDarkly AI Config")
        
        max_cost = ai_config.get("max_cost")
        if max_cost is None:
            raise ValueError("max_cost is required in LaunchDarkly AI Config")
        
        workflow_type = ai_config.get("workflow_type")
        if not workflow_type:
            raise ValueError("workflow_type is required in LaunchDarkly AI Config")
        
        return AgentConfig(
            variation_key=variation_key,
            model=model,
            instructions=instructions,
            allowed_tools=allowed_tools,
            max_tool_calls=max_tool_calls,
            max_cost=max_cost,
            workflow_type=workflow_type
        )