#!/usr/bin/env python3
"""
ConfigManager for LaunchDarkly AI Agent integration
"""
import os
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import ldclient
from ldclient import Context
from ldai.client import LDAIClient, LDAIAgent, LDAIAgentConfig, LDAIAgentDefaults, ModelConfig
from dotenv import load_dotenv

load_dotenv()

@dataclass
class AgentConfig:
    variation_key: str
    model: str
    instructions: str
    allowed_tools: List[str]
    tool_configs: Optional[Dict[str, Any]] = None
    max_tool_calls: int = 8
    workflow_type: str = "sequential"
    tracker: Optional[object] = None

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
    
    async def get_ai_config_with_tracker(self, user_id: str, config_key: str = None, user_context: dict = None):
        """Get AI Agent with tracker for Agent Mode"""
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
        
        agent = self.ai_client.agent(agent_config, ld_user_context)
        tracker = getattr(agent, 'tracker', None)
        
        return agent, tracker
    
    async def get_config(self, user_id: str, config_key: str = None, user_context: dict = None) -> AgentConfig:
        """Get agent configuration with AI metrics tracking"""
        ai_config, tracker = await self.get_ai_config_with_tracker(user_id, config_key, user_context)
        config = self._parse_ai_config_object(ai_config)
        config.tracker = tracker
        return config
    
    def _parse_ai_config_object(self, ai_config) -> AgentConfig:
        """Parse AIConfig/LDAIAgent object from LaunchDarkly AI SDK"""
        # Extract model name
        if hasattr(ai_config, 'model') and hasattr(ai_config.model, 'name'):
            model = ai_config.model.name
        else:
            model = "claude-3-haiku-20240307"
        
        # Extract instructions from LaunchDarkly Agent
        if hasattr(ai_config, 'instructions') and ai_config.instructions:
            instructions = ai_config.instructions
        else:
            instructions = "You are a helpful assistant."
        
        # Extract tools and configurations
        allowed_tools = []
        tool_configs = {}
        max_tool_calls = 8
        
        try:
            config_dict = ai_config.to_dict()
            
            # Extract tools from various possible locations
            if 'tools' in config_dict and config_dict['tools']:
                allowed_tools = list(config_dict['tools'])
            elif 'tool_list' in config_dict and config_dict['tool_list']:
                allowed_tools = list(config_dict['tool_list'])
            elif 'model' in config_dict and 'parameters' in config_dict['model'] and 'tools' in config_dict['model']['parameters']:
                tools_data = config_dict['model']['parameters']['tools']
                for tool in tools_data:
                    if 'name' in tool:
                        tool_name = tool['name']
                        allowed_tools.append(tool_name)
                        tool_configs[tool_name] = tool.get('parameters', {})
            
            # Extract max_tool_calls from customParameters
            if 'customParameters' in config_dict and config_dict['customParameters']:
                custom_params = config_dict['customParameters']
                if 'max_tool_calls' in custom_params:
                    max_tool_calls = custom_params['max_tool_calls']
            elif 'model' in config_dict and 'custom' in config_dict['model'] and config_dict['model']['custom']:
                custom_params = config_dict['model']['custom']
                if 'max_tool_calls' in custom_params:
                    max_tool_calls = custom_params['max_tool_calls']
                    
        except Exception:
            # Fallback to direct attribute access
            if hasattr(ai_config, 'tools') and ai_config.tools:
                allowed_tools = list(ai_config.tools)
            if hasattr(ai_config, 'custom') and hasattr(ai_config.custom, 'max_tool_calls'):
                max_tool_calls = ai_config.custom.max_tool_calls
        
        return AgentConfig(
            variation_key="default",
            model=model,
            instructions=instructions,
            allowed_tools=allowed_tools,
            tool_configs=tool_configs,
            max_tool_calls=max_tool_calls,
            workflow_type="sequential"
        )
    
    def track_metrics(self, tracker, func):
        """Track metrics with LaunchDarkly"""
        if not tracker:
            return func()
        
        try:
            from ai_metrics.metrics_tracker import track_langchain_metrics
            result = track_langchain_metrics(tracker, func)
            
            # Track additional metrics
            tracker.track_success()
            
            # Track token usage if available
            if hasattr(result, 'usage_metadata') and result.usage_metadata:
                from ldai.tracker import TokenUsage
                usage_data = result.usage_metadata
                token_usage = TokenUsage(
                    input=usage_data.get("input_tokens", 0),
                    output=usage_data.get("output_tokens", 0),
                    total=usage_data.get("total_tokens", 0)
                )
                tracker.track_tokens(token_usage)
            
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
