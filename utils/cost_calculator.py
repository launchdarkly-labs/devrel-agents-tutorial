"""
Cost Calculator for AI Model Usage

Calculates costs for token usage across different AI model providers.
Includes comprehensive pricing for all models used in the codebase.
"""

# Model pricing per 1 million tokens (in USD)
MODEL_PRICING = {
    # OpenAI Models
    "gpt-4o": {"input": 6.00, "output": 18.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o-mini-2024-07-18": {"input": 0.15, "output": 0.60},
    "chatgpt-4o-latest": {"input": 6.00, "output": 18.00},

    # Anthropic Claude Models - All Versions Found in Codebase
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku-20241022": {"input": 0.25, "output": 1.25},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    "claude-3-7-sonnet-latest": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet-latest": {"input": 3.00, "output": 15.00},
    "claude-opus-4-20250514": {"input": 20.00, "output": 80.00},

    # Mistral Models (Free as specified)
    "mistral-small-latest": {"input": 0.0, "output": 0.0},
    "mistral-small": {"input": 0.0, "output": 0.0},
    "mistral-medium": {"input": 0.0, "output": 0.0},
    "mistral-large": {"input": 0.0, "output": 0.0},

    # LaunchDarkly Provider-Prefixed Names (from create_configs.py mapping)
    "Anthropic.claude-3-7-sonnet-latest": {"input": 3.00, "output": 15.00},
    "Anthropic.claude-3-5-haiku-20241022": {"input": 0.25, "output": 1.25},
    "OpenAI.gpt-4o": {"input": 6.00, "output": 18.00},
    "OpenAI.gpt-4o-mini-2024-07-18": {"input": 0.15, "output": 0.60},
    "Mistral.mistral-small-latest": {"input": 0.0, "output": 0.0},
}


def calculate_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculate cost in USD for token usage.

    Args:
        model_name: Name of the AI model
        input_tokens: Number of input tokens used
        output_tokens: Number of output tokens generated

    Returns:
        Total cost in USD (rounded to 6 decimal places)
    """
    if model_name not in MODEL_PRICING:
        print(f"Warning: Unknown model '{model_name}', defaulting to free")
        return 0.0

    pricing = MODEL_PRICING[model_name]
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    total_cost = input_cost + output_cost

    return round(total_cost, 6)  # Round to 6 decimal places for precision


def get_model_pricing(model_name: str) -> dict:
    """
    Get pricing information for a specific model.

    Args:
        model_name: Name of the AI model

    Returns:
        Dictionary with input and output pricing per 1M tokens
    """
    return MODEL_PRICING.get(model_name, {"input": 0.0, "output": 0.0})


def list_supported_models() -> list:
    """
    Get list of all supported models.

    Returns:
        List of model names with pricing information
    """
    return list(MODEL_PRICING.keys())