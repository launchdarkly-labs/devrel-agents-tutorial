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
        
        # Get AI Config from LaunchDarkly - this will use the default if flag doesn't exist
        ai_config = self.ld_client.variation(
            ai_config_key,
            user_context,
            {
                "model": "claude-3-5-sonnet-20240620",
                "instructions": "You are a helpful mythical pet support agent. You can help with dragon feeding, phoenix rebirth cycles, unicorn grooming, and other mythical creature care.",
                "allowed_tools": ["search_v1", "search_v2"],
                "max_tool_calls": 3,
                "max_cost": 0.10
            }
        )
        
        variation_key = self.ld_client.variation(
            "support-agent-variation",
            user_context,
            "baseline"
        )
        
        # Handle case where variation_key might be a complex object
        if isinstance(variation_key, dict):
            variation_key = ai_config.get("_ldMeta", {}).get("variationKey", "unknown")
        
        # Extract model name from LaunchDarkly AI Config structure
        model = ai_config.get("model", "claude-3-5-sonnet-20241022")
        if isinstance(model, dict) and "name" in model:
            model = model["name"]
        
        # Map LaunchDarkly model names to correct Anthropic model IDs
        model_mapping = {
            "claude-3-5-sonnet-20240620": "claude-3-5-sonnet-20241022", 
            "claude-3-5-sonnet-20241022": "claude-3-5-sonnet-20241022",
            "claude-3-5-sonnet": "claude-3-5-sonnet-20241022"
        }
        
        if model in model_mapping:
            model = model_mapping[model]
        
        
        return AgentConfig(
            variation_key=variation_key,
            model=model,
            instructions=ai_config.get("instructions", "You are a helpful mythical pet support agent."),
            allowed_tools=ai_config.get("allowed_tools", []),
            max_tool_calls=ai_config.get("max_tool_calls", 3),
            max_cost=ai_config.get("max_cost", 0.10)
        )