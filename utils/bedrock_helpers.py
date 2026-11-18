"""
Bedrock model ID utilities.

Auto-corrects direct model IDs to inference profiles to prevent Bedrock errors.
"""
import os

from utils.logger import log_debug, log_student


def is_inference_profile_id(model_id: str) -> bool:
    """Check if model ID is a Bedrock inference profile (has region prefix: us., eu., ap., etc.)."""
    if not model_id:
        return False

    # Inference profiles start with region prefix
    region_prefixes = ('us.', 'us-gov.', 'eu.', 'ap.', 'apac.', 'au.', 'jp.', 'ca.', 'sa.', 'af.', 'me.', 'global.')
    return model_id.startswith(region_prefixes)


def ensure_bedrock_inference_profile(model_id: str, aws_region: str = None) -> str:
    """
    Auto-correct direct Bedrock model IDs to inference profiles.

    claude-* → anthropic.claude-* → {region}.anthropic.claude-*
    Region from: BEDROCK_INFERENCE_REGION env var, AWS_REGION, or default 'us'
    """
    # Anthropic model names (the "Anthropic" provider in LaunchDarkly) become Bedrock model IDs
    if model_id.startswith('claude-'):
        model_id = f"anthropic.{model_id}"

    # Already an inference profile - return as-is
    if is_inference_profile_id(model_id):
        log_debug(f"BEDROCK: Model ID '{model_id}' is already an inference profile")
        return model_id

    # Priority: BEDROCK_INFERENCE_REGION > AWS_REGION > default "us"
    region_prefix = os.getenv('BEDROCK_INFERENCE_REGION')
    if not region_prefix:
        # Extract from AWS_REGION (e.g., us-east-1 → us)
        region_prefix = (aws_region or os.getenv('AWS_REGION', 'us-east-1')).split('-')[0]

    # Auto-correct direct model IDs to inference profiles
    if model_id.startswith(('anthropic.', 'amazon.', 'meta.')):
        # Convert: anthropic.claude-haiku-5-5
        # To:      us.anthropic.claude-haiku-5-5
        inference_profile_id = f"{region_prefix}.{model_id}"

        log_student("BEDROCK AUTO-CORRECT: Converted direct model ID to inference profile")
        log_student(f"  Original: {model_id}")
        log_student(f"  Corrected: {inference_profile_id}")
        log_student(f"  Region Prefix: {region_prefix}")
        log_student(f"  💡 TIP: Select Bedrock → {inference_profile_id} in your LaunchDarkly config to use it directly")

        return inference_profile_id

    # Unknown format - return as-is and let Bedrock handle it
    log_debug(f"BEDROCK: Model ID '{model_id}' format not recognized, using as-is")
    return model_id
