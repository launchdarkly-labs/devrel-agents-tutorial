"""LaunchDarkly AI agent helpers - model creation and metric tracking."""
import time
import os
from typing import Any
from langchain.chat_models import init_chat_model
from utils.logger import log_student
from langchain_aws import ChatBedrockConverse
from langchain_core.tools import StructuredTool
import boto3


class MaxToolCallsExceeded(Exception):
    """Raised when agent exceeds max_tool_calls limit."""
    pass


class ToolCallCounter:
    """Tracks tool invocations and enforces limits."""
    def __init__(self, max_calls: int):
        self.count = 0
        self.max_calls = max_calls

    def increment(self):
        self.count += 1
        if self.count > self.max_calls:
            raise MaxToolCallsExceeded(
                f"Tool call limit of {self.max_calls} exceeded. "
                "Please simplify your request or increase max_tool_calls in LaunchDarkly."
            )


# Rate limiting
_last_llm_call_time = 0
_min_call_interval = 1.0


def _rate_limit_llm_call():
    """Simple rate limiter for LLM calls."""
    global _last_llm_call_time
    elapsed = time.time() - _last_llm_call_time
    if elapsed < _min_call_interval:
        time.sleep(_min_call_interval - elapsed)
    _last_llm_call_time = time.time()


def map_provider_to_langchain(provider_name: str) -> str:
    """Map LaunchDarkly provider names to LangChain."""
    mapping = {
        'anthropic': 'bedrock',
        'bedrock': 'bedrock',
        'gemini': 'google_genai',
        'openai': 'openai',
        'mistral': 'mistralai'
    }
    return mapping.get(provider_name.lower(), provider_name.lower())


def create_bedrock_chat_model(model_id: str, session: boto3.Session, region: str, **kwargs):
    """Create ChatBedrockConverse model with auto-correction for inference profiles."""
    from utils.bedrock_helpers import ensure_bedrock_inference_profile

    corrected_model_id = ensure_bedrock_inference_profile(model_id, region)
    log_student(f"BEDROCK: Creating {corrected_model_id} in {region}")

    client = session.client('bedrock-runtime', region_name=region)
    return ChatBedrockConverse(
        client=client,
        model_id=corrected_model_id,
        region_name=region,
        **kwargs
    )


def create_model_for_config(provider: str, model: str, config_manager):
    """Create LangChain chat model based on provider and auth method."""
    from utils.bedrock_helpers import normalize_bedrock_provider

    normalized = normalize_bedrock_provider(provider)
    langchain_provider = map_provider_to_langchain(normalized)

    if langchain_provider == 'bedrock':
        auth_method = os.getenv('AUTH_METHOD', 'api-key').lower()
        if auth_method == 'sso' and hasattr(config_manager, 'boto3_session') and config_manager.boto3_session:
            return create_bedrock_chat_model(
                model_id=model,
                session=config_manager.boto3_session,
                region=config_manager.aws_region
            )
        else:
            fallback = 'anthropic' if provider.lower() == 'anthropic' else langchain_provider
            return init_chat_model(model=model, model_provider=fallback)
    elif langchain_provider == 'openai':
        # GPT-6 models accept function tools only on the Responses API
        return init_chat_model(model=model, model_provider=langchain_provider, use_responses_api=True)
    else:
        return init_chat_model(model=model, model_provider=langchain_provider)


def wrap_tool_with_counter(tool: Any, counter: ToolCallCounter) -> StructuredTool:
    """Wrap a tool to track and limit invocations."""
    original_run = tool._run if hasattr(tool, '_run') else None
    original_arun = tool._arun if hasattr(tool, '_arun') else None

    def counted_run(**kwargs) -> str:
        counter.increment()
        query = kwargs.get('query') or kwargs.get('search_query', '')
        log_student(f"TOOL CALL #{counter.count}/{counter.max_calls}: {tool.name} | Query: '{query}'")
        if original_run:
            return original_run(**kwargs)
        raise NotImplementedError(f"Tool {tool.name} has no _run method")

    async def counted_arun(**kwargs) -> str:
        counter.increment()
        query = kwargs.get('query') or kwargs.get('search_query', '')
        log_student(f"TOOL CALL #{counter.count}/{counter.max_calls}: {tool.name} | Query: '{query}'")
        if original_arun:
            return await original_arun(**kwargs)
        elif original_run:
            return original_run(**kwargs)
        raise NotImplementedError(f"Tool {tool.name} has no run method")

    return StructuredTool(
        name=tool.name,
        description=tool.description,
        func=counted_run,
        coroutine=counted_arun if original_arun or original_run else None,
        args_schema=tool.args_schema if hasattr(tool, 'args_schema') else None
    )
