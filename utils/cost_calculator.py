"""
Cost Calculator for AI Model Usage

Hybrid pricing: exact match → normalize inference profiles → pattern match by tier → return $0
Handles new Bedrock models automatically via pattern matching (Opus/Sonnet/Haiku tiers).
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
    "claude-opus-4-20250514": {"input": 15.00, "output": 75.00},

    # Mistral Models (Free as specified)
    "mistral-small-latest": {"input": 0.0, "output": 0.0},
    "mistral-small": {"input": 0.0, "output": 0.0},
    "mistral-medium": {"input": 0.0, "output": 0.0},
    "mistral-large": {"input": 0.0, "output": 0.0},

    # LaunchDarkly Provider-Prefixed Names (from create_configs.py mapping)
    "Anthropic.claude-3-7-sonnet-latest": {"input": 3.00, "output": 15.00},
    "Anthropic.claude-3-5-haiku-20241022": {"input": 0.25, "output": 1.25},
    "Anthropic.claude-opus-4-20250514": {"input": 15.00, "output": 75.00},
    "OpenAI.gpt-4o": {"input": 6.00, "output": 18.00},
    "OpenAI.gpt-4o-mini-2024-07-18": {"input": 0.15, "output": 0.60},
    "Mistral.mistral-small-latest": {"input": 0.0, "output": 0.0},
}


def get_pricing_by_pattern(model_name: str) -> dict:
    """
    Pattern match model tier for pricing (Opus/Sonnet/Haiku/GPT-4).

    Handles new Bedrock models automatically without code changes.
    Returns None if no pattern matches.
    """
    # Normalize: lowercase and remove common prefixes
    normalized = model_name.lower()
    normalized = normalized.replace('us.', '').replace('eu.', '').replace('ap.', '')
    normalized = normalized.replace('ca.', '').replace('sa.', '').replace('af.', '').replace('me.', '')
    normalized = normalized.replace('anthropic.', '').replace('amazon.', '').replace('meta.', '')

    # Anthropic Claude - Match by tier
    if 'opus' in normalized:
        return {"input": 15.00, "output": 75.00}  # Opus tier (flagship)
    elif 'sonnet' in normalized or 'claude-4' in normalized:
        return {"input": 3.00, "output": 15.00}   # Sonnet tier (balanced)
    elif 'haiku' in normalized:
        return {"input": 0.25, "output": 1.25}    # Haiku tier (fast)

    # OpenAI - Match by tier
    elif 'gpt-4o-mini' in normalized:
        return {"input": 0.15, "output": 0.60}    # GPT-4o-mini
    elif 'gpt-4' in normalized or 'gpt4' in normalized:
        return {"input": 6.00, "output": 18.00}   # GPT-4 tier

    # Mistral - Free tier
    elif 'mistral' in normalized:
        return {"input": 0.0, "output": 0.0}      # Free tier

    # No pattern match
    return None


def calculate_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculate cost in USD for token usage.

    Hybrid strategy: exact match → normalize → pattern match → $0
    Handles new Bedrock models automatically via tier matching.
    """
    pricing = None
    lookup_name = model_name
    match_type = None

    # Step 1: Try exact match in pricing table
    if model_name in MODEL_PRICING:
        pricing = MODEL_PRICING[model_name]
        lookup_name = model_name
        match_type = "exact"

    # Step 2: Try normalizing Bedrock inference profiles
    elif model_name not in MODEL_PRICING:
        from utils.bedrock_helpers import is_inference_profile_id, extract_base_model_from_inference_profile

        if is_inference_profile_id(model_name):
            lookup_name = extract_base_model_from_inference_profile(model_name)
            if lookup_name in MODEL_PRICING:
                pricing = MODEL_PRICING[lookup_name]
                match_type = "normalized"

    # Step 3: Try pattern-based fallback
    if pricing is None:
        pricing = get_pricing_by_pattern(model_name)
        if pricing is not None:
            lookup_name = model_name
            match_type = "pattern"

    # Step 4: Graceful degradation - return 0 for unknown models
    if pricing is None:
        print(f"💡 COST CALCULATOR: No pricing available for '{model_name}' (cost tracking skipped)")
        return 0.0

    # Calculate cost
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    total_cost = input_cost + output_cost

    # Log calculation with match type for transparency
    if match_type == "pattern":
        print(f"COST CALCULATED: ${total_cost:.6f} for {model_name} ({input_tokens} in, {output_tokens} out) [pattern match]")
    else:
        print(f"COST CALCULATED: ${total_cost:.6f} for {lookup_name} ({input_tokens} in, {output_tokens} out)")

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