#!/usr/bin/env python3
"""
Simplified ConfigManager for LaunchDarkly AI Agent integration
"""
import os
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from launchdarkly_ai_server import (
    create_handler,
    execute_and_track,
    get_client,
    init_client,
    inspect_config,
    parse_ai_config,
    shutdown,
    to_ld_context,
)
from launchdarkly_ai_server.tracking import parse_usage
from dotenv import load_dotenv
from utils.cost_calculator import calculate_cost
from utils.logger import log_student, log_debug
import boto3

load_dotenv()

# The AI SDK has no feedback API, so these are sent as custom events. LaunchDarkly's
# built-in feedback metrics listen for these exact keys.
FEEDBACK_POSITIVE_EVENT = "$ld:ai:feedback:user:positive"
FEEDBACK_NEGATIVE_EVENT = "$ld:ai:feedback:user:negative"

@dataclass
class ServedConfig:
    """One resolved AgentControl config, from LaunchDarkly or from local defaults."""

    key: str
    config: dict[str, Any]
    meta: dict[str, Any] = field(default_factory=dict)
    from_fallback: bool = False

    @property
    def enabled(self) -> bool:
        return True

    @property
    def instructions(self) -> str:
        return self.config.get("instructions") or ""

    @property
    def model_name(self) -> str:
        return (self.config.get("model") or {}).get("name") or "unknown"

    @property
    def provider_name(self) -> str:
        return (self.config.get("provider") or {}).get("name") or "unknown"

    @property
    def parameters(self) -> dict[str, Any]:
        return (self.config.get("model") or {}).get("parameters") or {}

    @property
    def custom(self) -> dict[str, Any]:
        """Custom model params (e.g. max_tool_calls)."""
        return (self.config.get("model") or {}).get("custom") or {}

    @property
    def tools(self) -> dict[str, Any]:
        return self.config.get("tools") or {}

    @property
    def variation_key(self) -> str:
        """The served variation. Local fallbacks have no variation, hence 'fallback'."""
        if self.from_fallback:
            return "fallback"
        return self.meta.get("variationKey") or "unknown"

    def track_data(self) -> dict[str, Any]:
        """Metadata attached to custom metric events for experiment attribution."""
        return {
            "version": self.meta.get("version", 1),
            "configKey": self.key,
            "variationKey": self.variation_key,
            "modelName": self.model_name,
            "providerName": self.provider_name,
        }


class FixedConfigManager:
    def __init__(self):
        """Initialize config defaults and the AWS session.

        The LaunchDarkly client is initialized lazily, because the current AI
        SDK's init_client is async and this constructor is not.
        """
        self.sdk_key = os.getenv('LD_SDK_KEY')
        if not self.sdk_key:
            raise ValueError("LD_SDK_KEY environment variable is required")

        # Load defaults from .ai_config_defaults.json
        self._load_config_defaults()

        # Initialize AWS Bedrock session for SSO authentication
        self._initialize_bedrock_session()

    async def _ensure_client(self) -> bool:
        """Initialize the shared LaunchDarkly client. init_client is idempotent, so
        this is safe to await on every request.

        Returns False if the client can't connect, so get_config serves the
        local defaults.
        """
        try:
            await init_client({"sdkKey": self.sdk_key})
            return True
        except RuntimeError as e:
            log_student(f"CONFIG MANAGER: LaunchDarkly client unavailable: {e}")
            return False

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

    def _load_config_defaults(self):
        """Load AI config defaults from .ai_config_defaults.json

        This file is generated by the CI/CD test suite (ld-aic test) and contains
        the latest validated configs from LaunchDarkly production.
        """
        defaults_path = Path(".ai_config_defaults.json")

        if not defaults_path.exists():
            raise FileNotFoundError(
                "❌ .ai_config_defaults.json not found!\n\n"
                "This file contains fallback AI config defaults and should be generated by:\n"
                "  1. Running CI/CD tests: The 'ld-aic test' command automatically creates it\n"
                "  2. Manual generation: Run 'ld-aic validate' locally\n\n"
                "To generate it now:\n"
                "  ld-aic validate --config-keys 'supervisor-agent,support-agent,security-agent'\n\n"
                "Or if you have the CI/CD workflow running, it will be created automatically."
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
                f"❌ Failed to parse .ai_config_defaults.json: {e}\n\n"
                "The file may be corrupted. Regenerate it by running:\n"
                "  ld-aic validate --config-keys 'supervisor-agent,support-agent,security-agent'"
            )

    @staticmethod
    def _normalize_tools(config_data: dict[str, Any], config_key: str) -> dict[str, Any]:
        """Move a top-level `tools` array to `model.parameters.tools`.

        ld-aic writes tools at the top level of `.ai_config_defaults.json`, but
        LaunchDarkly serves them in `model.parameters.tools`, which is where the
        agents read them. The SDK also rejects a top-level `tools` array.
        """
        tools = config_data.pop("tools", None)
        if not isinstance(tools, list):
            if tools is not None:
                config_data["tools"] = tools
            return config_data

        model = config_data.setdefault("model", {})
        parameters = model.setdefault("parameters", {})
        parameters.setdefault("tools", tools)
        log_debug(
            f"DEFAULTS: moved {len(tools)} tools into model.parameters for '{config_key}'"
        )
        return config_data

    def _get_default_config(self, config_key: str) -> dict[str, Any]:
        """Get the fallback config for a key from .ai_config_defaults.json

        The file is written in the same shape the SDK parses, so this strips the
        `enabled` flag and validates the rest with the SDK's own parser rather
        than trusting it.

        Raises:
            ValueError: If the key is missing, disabled, or fails validation.
        """
        if config_key not in self.config_defaults:
            available_keys = list(self.config_defaults.keys())
            raise ValueError(
                f"❌ Config '{config_key}' not found in .ai_config_defaults.json!\n\n"
                f"Available configs: {', '.join(available_keys)}\n\n"
                "To add this config:\n"
                "  1. Create it in LaunchDarkly dashboard\n"
                f"  2. Run: ld-aic validate --config-keys '{config_key},...'\n"
                "  3. The config will be added to .ai_config_defaults.json"
            )

        config_data = dict(self.config_defaults[config_key])
        config_data = self._normalize_tools(config_data, config_key)

        if not config_data.pop("enabled", True):
            raise ValueError(
                f"❌ Fallback config '{config_key}' is marked disabled in "
                ".ai_config_defaults.json, so there is nothing to serve."
            )

        result = parse_ai_config(config_data)
        if not result.success:
            raise ValueError(
                f"❌ Fallback config '{config_key}' in .ai_config_defaults.json is "
                f"not a valid AI config: {result.error.get('message')}\n\n"
                "Regenerate it by running:\n"
                f"  ld-aic validate --config-keys '{config_key},...'"
            )

        return result.data

    def build_context(self, user_id: str, user_context: dict = None) -> dict[str, Any]:
        """Build a LaunchDarkly context with consistent attributes.

        This ensures the same context is used for both AI Config evaluation
        and custom metric tracking, which is required for experiment association.
        """
        context: dict[str, Any] = {"kind": "user", "key": user_id}

        if user_context:
            # Set all attributes from user_context for consistency
            for key, value in user_context.items():
                context[key] = value
                log_debug(f"CONFIG MANAGER: Set {key}={value}")

        return context

    async def get_config(self, user_id: str, config_key: str = None, user_context: dict = None) -> ServedConfig:
        """Get LaunchDarkly AI Config with fallback to .ai_config_defaults.json

        Fallback chain:
        1. Try LaunchDarkly (live config with targeting)
        2. If that fails, use .ai_config_defaults.json (validated production defaults)
        3. If config not in defaults file, raise helpful error
        """
        log_debug(f"CONFIG MANAGER: Getting config for user_id={user_id}, config_key={config_key}")
        log_debug(f"CONFIG MANAGER: User context: {user_context}")

        client_ready = await self._ensure_client()

        # Build context using centralized method
        ld_user_context = self.build_context(user_id, user_context)
        log_debug(f"CONFIG MANAGER: Built LaunchDarkly context: {ld_user_context}")

        ai_config_key = config_key or os.getenv('LAUNCHDARKLY_AI_CONFIG_KEY', 'support-agent')
        log_debug(f"CONFIG MANAGER: Using AI config key: {ai_config_key}")

        inspected = (
            await inspect_config(ai_config_key, ld_user_context)
            if client_ready
            else {"enabled": False, "config": None, "meta": None}
        )

        if inspected["enabled"] and inspected["config"]:
            served = ServedConfig(
                key=ai_config_key,
                config=inspected["config"],
                meta=inspected["meta"] or {},
            )
            log_debug("CONFIG MANAGER: ✅ Got config from LaunchDarkly")
            log_debug(f"CONFIG MANAGER: Model: {served.model_name}")
            log_debug(f"CONFIG MANAGER: Variation: {served.variation_key}")
            return served

        # LaunchDarkly is unavailable, the key is unknown, or targeting is off.
        log_student(
            f"CONFIG MANAGER: '{ai_config_key}' not served by LaunchDarkly; "
            "using .ai_config_defaults.json"
        )
        served = ServedConfig(
            key=ai_config_key,
            config=self._get_default_config(ai_config_key),
            from_fallback=True,
        )
        log_debug(f"CONFIG MANAGER: Fallback model: {served.model_name}")
        return served

    async def track(self, served: ServedConfig, context: dict, call, user_input: str = None):
        """Run a model call and record it in LaunchDarkly.

        `call` is an async function that returns (result, usage), with usage in
        LangChain's usage_metadata shape. The SDK records duration, tokens, and
        success or error. The cost goes out as the ai_cost_per_request event
        that Tutorial 3's experiments measure. A local fallback has no variation
        for the SDK metrics, so only the cost is sent.
        """
        box = {}

        async def handler(*_):
            box["result"], usage = await call()
            return {"output": "", "usage": usage or {}}

        if served.from_fallback:
            usage = parse_usage((await handler())["usage"])
            track_data = served.track_data()
        else:
            tracked = await execute_and_track(
                config_key=served.key,
                config=served.config,
                meta=served.meta,
                user_context=context,
                handler=create_handler((served.provider_name, "agent"), handler),
                user_input=user_input,
            )
            usage, track_data = tracked["usage"], tracked["track_data"]

        if usage["total"] > 0:
            log_student(f"{served.key.upper()} TOKENS: {usage['total']} ({usage['input']} in, {usage['output']} out)")
            cost = calculate_cost(served.model_name, usage["input"], usage["output"])
            if cost > 0:
                try:
                    self._track("ai_cost_per_request", context, track_data, cost)
                except Exception as e:
                    log_debug(f"COST TRACKING ERROR: {e}")

        return box["result"]

    def _flush(self):
        """Flush pending events if the client is up.

        The client is initialized lazily on the first get_config, so this can be
        called before it exists (ConfigManager does so at startup). get_client
        raises in that state, and there is nothing buffered to flush anyway.
        """
        try:
            get_client().flush()
        except Exception as e:
            log_debug(f"FLUSH SKIPPED (client not initialized yet): {e}")

    def clear_cache(self):
        """Flush pending LaunchDarkly events"""
        self._flush()

    def flush_metrics(self):
        """Flush metrics to LaunchDarkly"""
        self._flush()

    @staticmethod
    def _track(event: str, context: dict, data, value):
        """Send a custom event. LDClient.track needs a Context, not a dict."""
        client = get_client()
        client.track(event, to_ld_context(client, context), data, value)
        client.flush()

    def track_feedback(self, served: Optional[ServedConfig], context, thumbs_up: bool) -> bool:
        """Track user feedback with LaunchDarkly, attributed to the served variation."""
        if not served:
            return False

        try:
            event = FEEDBACK_POSITIVE_EVENT if thumbs_up else FEEDBACK_NEGATIVE_EVENT
            self._track(event, context, served.track_data(), 1)
            log_student(f"FEEDBACK TRACKED: {'👍 Positive' if thumbs_up else '👎 Negative'}")
            return True
        except Exception as e:
            log_debug(f"FEEDBACK TRACKING ERROR: {e}")
            return False

    async def close(self):
        """Flush pending LaunchDarkly events and spans, then close the client"""
        try:
            await shutdown()
        except Exception as e:
            log_debug(f"CLOSE ERROR: {e}")
