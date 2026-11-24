"""
Cost Calculator for AI Model Usage

Prices are USD per 1 million tokens, from the LaunchDarkly model catalog. Mistral
is $0 because the tutorial uses Mistral's free tier.
"""

MODEL_PRICING = {
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50},
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00},
    "claude-opus-5-5": {"input": 4.00, "output": 20.00},
    "gpt-6-luna": {"input": 0.10, "output": 0.50},
    "gpt-6.1-terra": {"input": 1.00, "output": 5.00},
    "gpt-6.2-sol": {"input": 2.00, "output": 10.00},
    "mistral-small-latest": {"input": 0.0, "output": 0.0},
}

# Bedrock model IDs carry region and version affixes, so price them by Claude tier.
TIER_PRICING = {
    "opus": MODEL_PRICING["claude-opus-5-5"],
    "sonnet": MODEL_PRICING["claude-sonnet-5-5"],
    "haiku": MODEL_PRICING["claude-haiku-5-5"],
}


def calculate_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost in USD for token usage. Unknown models cost $0."""
    pricing = MODEL_PRICING.get(model_name) or next(
        (price for tier, price in TIER_PRICING.items() if tier in model_name.lower()), None
    )
    if pricing is None:
        print(f"💡 COST CALCULATOR: No pricing available for '{model_name}' (cost tracking skipped)")
        return 0.0

    total_cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
    print(f"COST CALCULATED: ${total_cost:.6f} for {model_name} ({input_tokens} in, {output_tokens} out)")
    return round(total_cost, 6)
