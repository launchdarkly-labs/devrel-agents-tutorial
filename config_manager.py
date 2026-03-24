#!/usr/bin/env python3
"""
Simplified ConfigManager for LaunchDarkly AI Agent integration
"""
import os
import json
from pathlib import Path
import ldclient
from ldclient import Context
from ldai.client import LDAIClient, AIAgentConfigDefault, ModelConfig, ProviderConfig
from ldai.tracker import FeedbackKind
from dotenv import load_dotenv
from utils.logger import log_student, log_debug
import boto3

load_dotenv()

class FixedConfigManager:
    def __init__(self):
        """Initialize LaunchDarkly client and AI client"""
        self.sdk_key = os.getenv('LD_SDK_KEY')
        if not self.sdk_key:
            raise ValueError("LD_SDK_KEY environment variable is required")

        # Load defaults from .ai_config_defaults.json
        self._load_config_defaults()

        self._initialize_launchdarkly_client()

        # Initialize AWS Bedrock session for SSO authentication
        self._initialize_bedrock_session()

    def _load_config_defaults(self):
        """Load AI config defaults from .ai_config_defaults.json

        This file contains fallback configs used when LaunchDarkly is unavailable.
        It's created by the bootstrap script: python bootstrap/create_configs.py
        """
        defaults_path = Path(".ai_config_defaults.json")

        if not defaults_path.exists():
            raise FileNotFoundError(
                ".ai_config_defaults.json not found!\n\n"
                "Run the bootstrap script to create AI Configs and generate this file:\n"
                "  python bootstrap/create_configs.py"
            )

        try:
            with open(defaults_path, 'r') as f:
                data = json.load(f)

            self.config_defaults = data.get("configs", {})
            metadata = data.get("_metadata", {})

            log_debug(f"DEFAULTS: Loaded {len(self.config_defaults)} config defaults from {metadata.get('environment', 'unknown')}")
            log_debug(f"DEFAULTS: Generated at {metadata.get('generated_at', 'unknown')}")

        except json.JSONDecodeError as e:
            raise ValueError(
                f"Failed to parse .ai_config_defaults.json: {e}\n\n"
                "The file may be corrupted. Regenerate it by running:\n"
                "  python bootstrap/create_configs.py"
            )

    def _get_default_config(self, config_key: str) -> AIAgentConfigDefault:
        """Get fallback config from .ai_config_defaults.json

        Args:
            config_key: The AI config key (e.g., 'support-agent')

        Returns:
            AIAgentConfigDefault object with config from the defaults file

        Raises:
            ValueError: If config key not found in defaults
        """
        if config_key not in self.config_defaults:
            available_keys = list(self.config_defaults.keys())
            raise ValueError(
                f"Config '{config_key}' not found in .ai_config_defaults.json!\n\n"
                f"Available configs: {', '.join(available_keys)}\n\n"
                "To add this config, create it in LaunchDarkly and run:\n"
                "  python bootstrap/create_configs.py"
            )

        config_data = self.config_defaults[config_key]

        # Convert JSON config to AIAgentConfigDefault
        # Note: Tools are managed by LaunchDarkly and not part of defaults
        return AIAgentConfigDefault(
            enabled=config_data.get("enabled", True),
            model=ModelConfig(
                name=config_data["model"]["name"],
                parameters=config_data["model"].get("parameters", {})
            ),
            provider=ProviderConfig(
                name=config_data["provider"]["name"]
            ),
            instructions=config_data.get("instructions", "You are a helpful assistant.")
        )
    
    def _initialize_launchdarkly_client(self):
        """Initialize LaunchDarkly client and AI client"""
        config = ldclient.Config(self.sdk_key)
        ldclient.set_config(config)
        self.ld_client = ldclient.get()

        # Wait for initialization (SDK 9.x pattern)
        import time
        for _ in range(100):  # Wait up to 10 seconds
            if self.ld_client.is_initialized():
                break
            time.sleep(0.1)

        if not self.ld_client.is_initialized():
            raise RuntimeError("LaunchDarkly client initialization failed")

        self.ai_client = LDAIClient(self.ld_client)

    def _initialize_bedrock_session(self):
        """Initialize AWS Bedrock session if AUTH_METHOD=sso"""
        auth_method = os.getenv('AUTH_METHOD', 'api-key').lower()

        if auth_method != 'sso':
            self.boto3_session = None
            log_debug("AUTH_METHOD not set to 'sso', Bedrock unavailable")
            return

        try:
            # Initialize AWS session with optional profile support
            aws_region = os.getenv('AWS_REGION', 'us-east-1')
            aws_profile = os.getenv('AWS_PROFILE')

            # Create session with profile if specified, otherwise use default credentials
            if aws_profile:
                self.boto3_session = boto3.Session(
                    region_name=aws_region,
                    profile_name=aws_profile
                )
                log_debug(f"AWS: Using profile '{aws_profile}' in region {aws_region}")
            else:
                self.boto3_session = boto3.Session(region_name=aws_region)
                log_debug(f"AWS: Using default credentials in region {aws_region}")

            self.aws_region = aws_region
            self.aws_profile = aws_profile

            # Test current SSO session
            sts = self.boto3_session.client('sts')
            identity = sts.get_caller_identity()
            user_name = identity['Arn'].split('/')[-1]
            account = identity['Account']
            log_student(f"AWS: Connected via SSO as {user_name} (Account: {account})")

        except Exception as e:
            log_student(f"AWS SSO session not available: {e}")

            # Provide helpful login command with profile if specified
            profile_hint = f" --profile {os.getenv('AWS_PROFILE')}" if os.getenv('AWS_PROFILE') else ""
            log_student(f"Run: aws sso login{profile_hint}")
            raise

    def build_context(self, user_id: str, user_context: dict = None) -> Context:
        """Build a LaunchDarkly context with consistent attributes.

        This ensures the same context is used for AI Config evaluation
        and standard tracking.
        """
        context_builder = Context.builder(user_id).kind('user')
        
        if user_context:
            # Set all attributes from user_context for consistency
            for key, value in user_context.items():
                context_builder.set(key, value)
                log_debug(f"CONFIG MANAGER: Set {key}={value}")
        
        return context_builder.build()
    

    async def get_config(self, user_id: str, config_key: str = None, user_context: dict = None):
        """Get LaunchDarkly AI Config with fallback to .ai_config_defaults.json

        Fallback chain:
        1. Try LaunchDarkly (live config with targeting)
        2. If that fails, use .ai_config_defaults.json (validated production defaults)
        3. If config not in defaults file, raise helpful error
        """
        log_debug(f"CONFIG MANAGER: Getting config for user_id={user_id}, config_key={config_key}")
        log_debug(f"CONFIG MANAGER: User context: {user_context}")

        # Build context using centralized method
        ld_user_context = self.build_context(user_id, user_context)
        log_debug(f"CONFIG MANAGER: Built LaunchDarkly context: {ld_user_context}")

        ai_config_key = config_key or os.getenv('LAUNCHDARKLY_AI_CONFIG_KEY', 'support-agent')
        log_debug(f"CONFIG MANAGER: Using AI config key: {ai_config_key}")

        # Load default from .ai_config_defaults.json (fails with helpful error if not found)
        default_config = self._get_default_config(ai_config_key)
        log_debug(f"CONFIG MANAGER: Loaded fallback default - model: {default_config.model.name}")

        # Call LaunchDarkly using new SDK pattern - agent_config(key, context, default)
        result = self.ai_client.agent_config(ai_config_key, ld_user_context, default=default_config)
        log_debug("CONFIG MANAGER: ✅ Got config (from LaunchDarkly or fallback)")

        # Debug the actual configuration received (basic info only)
        try:
            config_dict = result.to_dict()
            log_debug(f"CONFIG MANAGER: Model: {config_dict.get('model', {}).get('name', 'unknown')}")
            if hasattr(result, 'tracker') and hasattr(result.tracker, '_variation_key'):
                log_debug(f"CONFIG MANAGER: Variation: {result.tracker._variation_key}")
        except Exception as debug_e:
            log_debug(f"CONFIG MANAGER: Could not debug result: {debug_e}")

        return result
    

    def flush(self):
        """Flush metrics and clear SDK cache"""
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
            self.ld_client.close()
        except Exception:
            pass