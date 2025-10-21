#!/usr/bin/env python3
"""
Simplified ConfigManager for LaunchDarkly AI Agent integration
"""
import os
import time
import ldclient
from ldclient import Context
from ldai.client import LDAIClient, LDAIAgentConfig, LDAIAgentDefaults, ModelConfig
from ldai.tracker import FeedbackKind
from dotenv import load_dotenv
from utils.logger import log_student, log_debug
import boto3

load_dotenv()

def map_provider_to_langchain(provider_name):
    """Map LaunchDarkly provider names to LangChain provider names."""
    provider_mapping = {
        'anthropic': 'bedrock',   # CHANGED: Route through Bedrock
        'bedrock': 'bedrock',     # NEW: Explicit Bedrock provider
        'gemini': 'google_genai',
        'openai': 'openai',
        'mistral': 'mistralai'
    }
    lower_provider = provider_name.lower()
    return provider_mapping.get(lower_provider, lower_provider)

class FixedConfigManager:
    def __init__(self):
        """Initialize LaunchDarkly client and AI client"""
        self.sdk_key = os.getenv('LD_SDK_KEY')
        if not self.sdk_key:
            raise ValueError("LD_SDK_KEY environment variable is required")

        self._initialize_launchdarkly_client()
        self._initialize_ai_client()

        # ADD THIS: Initialize AWS Bedrock session
        self._initialize_bedrock_session()
    
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

    def _initialize_bedrock_session(self):
        """Initialize AWS Bedrock session if AUTH_METHOD=sso"""
        auth_method = os.getenv('AUTH_METHOD', 'api-key').lower()

        if auth_method != 'sso':
            self.boto3_session = None
            log_debug("AUTH_METHOD not set to 'sso', Bedrock unavailable")
            return

        try:
            # Use default AWS profile (whatever user is logged in as)
            aws_region = os.getenv('AWS_REGION', 'us-east-1')
            self.boto3_session = boto3.Session(region_name=aws_region)  # No profile_name!
            self.aws_region = aws_region

            # Test current SSO session
            sts = self.boto3_session.client('sts')
            identity = sts.get_caller_identity()
            user_name = identity['Arn'].split('/')[-1]
            account = identity['Account']
            log_student(f"AWS: Connected via SSO as {user_name} (Account: {account})")

        except Exception as e:
            log_student(f"AWS SSO session not available: {e}")
            log_student("Run: aws sso login")  # Don't specify profile
            raise

    def validate_bedrock_access(self):
        """Validate Bedrock access and model availability for Bedrock-only deployment."""
        if not self.boto3_session:
            raise ValueError("Bedrock session not initialized. Set AUTH_METHOD=sso and run: aws sso login")

        try:
            # Test Bedrock service access
            bedrock_client = self.boto3_session.client('bedrock', region_name=self.aws_region)

            # List available foundation models to verify access
            response = bedrock_client.list_foundation_models()
            available_models = [model['modelId'] for model in response.get('modelSummaries', [])]

            # Check for Claude models specifically
            claude_models = [model for model in available_models if 'anthropic.claude' in model]
            if claude_models:
                log_student(f"BEDROCK VALIDATION: ✓ Found {len(claude_models)} Claude models available")
                log_debug(f"BEDROCK VALIDATION: Available Claude models: {claude_models[:3]}...")  # Show first 3
            else:
                log_student("BEDROCK VALIDATION: ⚠️  No Claude models found. Request access in AWS console.")

            # Check for Titan embeddings
            titan_models = [model for model in available_models if 'amazon.titan-embed' in model]
            if titan_models:
                log_student(f"BEDROCK VALIDATION: ✓ Found {len(titan_models)} Titan embedding models")
                log_debug(f"BEDROCK VALIDATION: Available Titan models: {titan_models}")
            else:
                log_student("BEDROCK VALIDATION: ⚠️  No Titan embedding models found. Request access in AWS console.")

            log_student(f"BEDROCK VALIDATION: ✓ Successfully validated access to {len(available_models)} total models")
            return True

        except Exception as e:
            log_student(f"BEDROCK VALIDATION: ✗ Failed to validate Bedrock access: {e}")
            if 'AccessDenied' in str(e):
                log_student("BEDROCK VALIDATION: Request Bedrock model access in AWS Console")
            return False

    def validate_hybrid_configuration(self):
        """
        Validate hybrid provider configurations and provide guidance.

        Returns dict with validation results, warnings, and recommendations.
        """
        auth_method = os.getenv('AUTH_METHOD', 'api-key').lower()
        embedding_provider = os.getenv('EMBEDDING_PROVIDER', '').lower()
        has_openai = bool(os.getenv('OPENAI_API_KEY'))
        has_anthropic = bool(os.getenv('ANTHROPIC_API_KEY'))

        # Determine embedding and chat providers
        if embedding_provider == 'openai':
            embedding_provider_actual = 'openai'
        elif embedding_provider == 'bedrock':
            embedding_provider_actual = 'bedrock'
        elif auth_method == 'sso' and not has_openai:
            embedding_provider_actual = 'bedrock'
        elif has_openai:
            embedding_provider_actual = 'openai'
        else:
            embedding_provider_actual = 'openai'  # Default

        # Chat provider (determined by AUTH_METHOD)
        if auth_method == 'sso':
            chat_provider = 'bedrock'
        else:
            chat_provider = 'api-keys'

        result = {
            "valid": True,
            "configuration": {
                "chat_provider": chat_provider,
                "embedding_provider": embedding_provider_actual,
                "auth_method": auth_method,
                "embedding_explicit": bool(embedding_provider)
            },
            "warnings": [],
            "recommendations": []
        }

        # Validate hybrid scenarios
        if chat_provider == 'bedrock' and embedding_provider_actual == 'openai':
            # Hybrid: Bedrock chat + OpenAI embeddings
            if not has_openai:
                result["valid"] = False
                result["warnings"].append(
                    "Hybrid config requires OPENAI_API_KEY for OpenAI embeddings"
                )
            else:
                result["recommendations"].append(
                    "✅ Hybrid setup: Bedrock chat models with OpenAI embeddings"
                )
                log_debug("HYBRID: Bedrock chat + OpenAI embeddings configuration detected")

        elif chat_provider == 'api-keys' and embedding_provider_actual == 'bedrock':
            # Hybrid: API keys chat + Bedrock embeddings
            if not self.boto3_session:
                result["valid"] = False
                result["warnings"].append(
                    "Hybrid config requires AWS SSO for Bedrock embeddings. Run: aws sso login"
                )
            elif not (has_anthropic or has_openai):
                result["valid"] = False
                result["warnings"].append(
                    "Hybrid config requires API keys for chat models (ANTHROPIC_API_KEY or OPENAI_API_KEY)"
                )
            else:
                result["recommendations"].append(
                    "✅ Hybrid setup: Direct API chat models with Bedrock embeddings"
                )
                log_debug("HYBRID: API-key chat + Bedrock embeddings configuration detected")

        elif chat_provider == 'bedrock' and embedding_provider_actual == 'bedrock':
            # Full Bedrock
            result["recommendations"].append(
                "✅ Full Bedrock setup: Both chat and embeddings use AWS Bedrock"
            )
            log_debug("HYBRID: Full Bedrock configuration detected")

        elif chat_provider == 'api-keys' and embedding_provider_actual == 'openai':
            # Full API keys
            result["recommendations"].append(
                "✅ Full API setup: Both chat and embeddings use direct APIs"
            )
            log_debug("HYBRID: Full API-key configuration detected")

        # Additional validation
        if not embedding_provider and chat_provider != embedding_provider_actual:
            result["recommendations"].append(
                f"💡 Consider setting EMBEDDING_PROVIDER={embedding_provider_actual} to make configuration explicit"
            )

        return result
    
    def build_context(self, user_id: str, user_context: dict = None) -> Context:
        """Build a LaunchDarkly context with consistent attributes.
        
        This ensures the same context is used for both AI Config evaluation
        and custom metric tracking, which is required for experiment association.
        """
        context_builder = Context.builder(user_id).kind('user')
        
        if user_context:
            # Set all attributes from user_context for consistency
            for key, value in user_context.items():
                context_builder.set(key, value)
                log_debug(f"CONFIG MANAGER: Set {key}={value}")
        
        return context_builder.build()
    
    async def get_config(self, user_id: str, config_key: str = None, user_context: dict = None):
        """Get LaunchDarkly AI Config object directly - no wrapper"""
        log_debug(f"CONFIG MANAGER: Getting config for user_id={user_id}, config_key={config_key}")
        log_debug(f"CONFIG MANAGER: User context: {user_context}")
        
        # Build context using centralized method
        ld_user_context = self.build_context(user_id, user_context)
        log_debug(f"CONFIG MANAGER: Built LaunchDarkly context: {ld_user_context}")
        
        ai_config_key = config_key or os.getenv('LAUNCHDARKLY_AI_CONFIG_KEY', 'support-agent')
        log_debug(f"CONFIG MANAGER: Using AI config key: {ai_config_key}")
        
        agent_config = LDAIAgentConfig(
            key=ai_config_key,
            default_value=LDAIAgentDefaults(
                enabled=True,
                model=ModelConfig(name="claude-3-haiku-20240307"),
                instructions="You are a helpful assistant."
            )
        )
        
        try:
            # Return the AI Config object directly
            result = self.ai_client.agent(agent_config, ld_user_context)
            log_debug("CONFIG MANAGER: Got result from LaunchDarkly")
            
            # Debug the actual configuration received (basic info only)
            try:
                config_dict = result.to_dict()
                log_debug(f"CONFIG MANAGER: Model: {config_dict.get('model', {}).get('name', 'unknown')}")
                if hasattr(result, 'tracker') and hasattr(result.tracker, '_variation_key'):
                    log_debug(f"CONFIG MANAGER: Variation: {result.tracker._variation_key}")
            except Exception as debug_e:
                log_debug(f"CONFIG MANAGER: Could not debug result: {debug_e}")
            
            return result
        except Exception as e:
            log_student(f"CONFIG MANAGER ERROR: {e}")
            import traceback
            log_debug(f"CONFIG MANAGER ERROR TRACEBACK: {traceback.format_exc()}")
            raise
    

    def clear_cache(self):
        """Clear LaunchDarkly SDK cache"""
        self.ld_client.flush()

    def flush_metrics(self):
        """Flush metrics to LaunchDarkly"""
        self.ld_client.flush()

    def track_cost_metric(self, agent_config, context, cost, config_key):
        """Track cost metric with AI Config metadata for experiment attribution.
        
        This ensures cost events include trackJsonData so they're properly
        associated with AI Config variations in experiments, matching the
        pattern used by token and feedback tracking.
        
        Args:
            agent_config: The AI config object with tracker
            context: LaunchDarkly context
            cost: Cost value in dollars
            config_key: The AI config key (e.g., 'support-agent', 'security-agent')
        """
        try:
            # Extract metadata from agent_config for experiment attribution
            metadata = {
                "version": 1,
                "configKey": config_key,
                "variationKey": agent_config.tracker._variation_key if hasattr(agent_config.tracker, '_variation_key') else 'unknown',
                "modelName": agent_config.model.name if hasattr(agent_config, 'model') else 'unknown',
                "providerName": agent_config.provider.name if hasattr(agent_config, 'provider') else 'unknown'
            }
            
            # Track with metadata - this creates trackJsonData in the event
            self.ld_client.track("ai_cost_per_request", context, metadata, cost)
            self.ld_client.flush()
            
        except Exception as e:
            log_debug(f"COST TRACKING ERROR: {e}")
            # Fallback to basic tracking if metadata extraction fails
            self.ld_client.track("ai_cost_per_request", context, None, cost)
            self.ld_client.flush()

    def track_feedback(self, tracker, thumbs_up: bool):
        """Track user feedback with LaunchDarkly"""
        if not tracker:
            return False

        try:
            # Use LaunchDarkly's feedback tracking
            feedback_dict = {
                "kind": FeedbackKind.Positive if thumbs_up else FeedbackKind.Negative
            }
            tracker.track_feedback(feedback_dict)
            log_student(f"FEEDBACK TRACKED: {'👍 Positive' if thumbs_up else '👎 Negative'}")
            self.ld_client.flush()
            return True
        except Exception as e:
            log_debug(f"FEEDBACK TRACKING ERROR: {e}")
            return False

    def close(self):
        """Close LaunchDarkly client"""
        try:
            self.ld_client.flush()
        except Exception:
            pass
        try:
            self.ld_client.close()
        except Exception:
            pass