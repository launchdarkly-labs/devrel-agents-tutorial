"""
Bedrock provider and model ID normalization utilities.

Handles provider format variations (Bedrock, bedrock:anthropic, anthropic).
Auto-corrects direct model IDs to inference profiles to prevent Bedrock errors.
"""

from utils.logger import log_debug


def normalize_bedrock_provider(provider_name: str) -> str:
    """
    Normalize Bedrock provider formats to 'bedrock' for LangChain.

    Handles: Bedrock, bedrock:anthropic, anthropic → bedrock
    """
    if not provider_name:
        return provider_name

    lower_provider = provider_name.lower()

    # Handle bedrock:* format (e.g., "bedrock:anthropic" from structured output)
    if lower_provider.startswith('bedrock:'):
        log_debug(f"BEDROCK HELPER: Normalized '{provider_name}' → 'bedrock'")
        return 'bedrock'

    # Handle explicit "Bedrock" or "bedrock"
    if lower_provider == 'bedrock':
        return 'bedrock'

    # Handle legacy "anthropic" routing to Bedrock
    if lower_provider == 'anthropic':
        log_debug("BEDROCK HELPER: Routing 'anthropic' → 'bedrock'")
        return 'bedrock'

    # Return as-is for other providers
    return lower_provider


def is_inference_profile_id(model_id: str) -> bool:
    """Check if model ID is a Bedrock inference profile (has region prefix: us., eu., ap., etc.)."""
    if not model_id:
        return False

    # Inference profiles start with region prefix
    region_prefixes = ['us.', 'eu.', 'ap.', 'ca.', 'sa.', 'af.', 'me.']
    return any(model_id.startswith(prefix) for prefix in region_prefixes)


def extract_base_model_from_inference_profile(inference_profile_id: str) -> str:
    """
    Extract base model name from inference profile for pricing.

    us.anthropic.claude-3-5-sonnet-20241022-v2:0 → claude-3-5-sonnet-20241022
    """
    if not inference_profile_id:
        return inference_profile_id

    # Remove region prefix (e.g., "us.", "eu.")
    parts = inference_profile_id.split('.', 1)
    if len(parts) < 2:
        return inference_profile_id

    # Remove provider prefix (e.g., "anthropic.")
    model_with_version = parts[1]
    provider_parts = model_with_version.split('.', 1)
    if len(provider_parts) < 2:
        return inference_profile_id

    # Now we have something like "claude-3-5-sonnet-20241022-v2:0"
    full_model = provider_parts[1]

    # Map to base model name for pricing
    # Extract model family before version suffix
    model_base = full_model.rsplit('-', 1)[0] if '-v' in full_model or ':' in full_model else full_model

    # Map specific versions to pricing model names
    model_mapping = {
        'claude-3-5-sonnet-20241022': 'claude-3-5-sonnet-20241022',
        'claude-3-5-sonnet-20250219': 'claude-3-5-sonnet-latest',
        'claude-3-7-sonnet-20250219': 'claude-3-7-sonnet-latest',
        'claude-3-5-haiku-20241022': 'claude-3-5-haiku-20241022',
        'claude-opus-4-20250514': 'claude-opus-4-20250514',
    }

    return model_mapping.get(model_base, model_base)


def ensure_bedrock_inference_profile(model_id: str, aws_region: str = None) -> str:
    """
    Auto-correct direct Bedrock model IDs to inference profiles.

    anthropic.claude-* → {region}.anthropic.claude-*
    Region from: BEDROCK_INFERENCE_REGION env var, AWS_REGION, or default 'us'
    """
    import os

    # Already an inference profile - return as-is
    if is_inference_profile_id(model_id):
        log_debug(f"BEDROCK: Model ID '{model_id}' is already an inference profile")
        return model_id

    # Determine region prefix
    # Priority: BEDROCK_INFERENCE_REGION > AWS_REGION > default "us"
    region_prefix = os.getenv('BEDROCK_INFERENCE_REGION')

    if not region_prefix:
        # Extract from AWS_REGION (e.g., us-east-1 → us)
        if aws_region:
            region_prefix = aws_region.split('-')[0]
        else:
            region_from_env = os.getenv('AWS_REGION', 'us-east-1')
            region_prefix = region_from_env.split('-')[0]

    # Auto-correct direct model IDs to inference profiles
    if model_id.startswith('anthropic.') or model_id.startswith('amazon.') or model_id.startswith('meta.'):
        # Convert: anthropic.claude-3-7-sonnet-20250219-v1:0
        # To:      us.anthropic.claude-3-7-sonnet-20250219-v1:0
        inference_profile_id = f"{region_prefix}.{model_id}"

        from utils.logger import log_student
        log_student("BEDROCK AUTO-CORRECT: Converted direct model ID to inference profile")
        log_student(f"  Original: {model_id}")
        log_student(f"  Corrected: {inference_profile_id}")
        log_student(f"  Region Prefix: {region_prefix}")
        log_student(f"  💡 TIP: Update your LaunchDarkly AI Config to use '{inference_profile_id}' directly")

        return inference_profile_id

    # Unknown format - return as-is and let Bedrock handle it
    log_debug(f"BEDROCK: Model ID '{model_id}' format not recognized, using as-is")
    return model_id


def get_bedrock_validation_guidance(model_id: str) -> str:
    """Provide guidance for Bedrock model configuration issues."""
    if not is_inference_profile_id(model_id):
        return (
            f"⚠️  BEDROCK CONFIG ERROR: '{model_id}' is a direct model ID.\n"
            f"   Update to inference profile format: 'us.anthropic.claude-*'\n"
            f"   Set BEDROCK_INFERENCE_REGION in .env to control region prefix."
        )
    return ""
