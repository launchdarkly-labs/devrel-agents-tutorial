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
    execute_and_track,
    get_client,
    init_client,
    inspect_config,
    parse_ai_config,
    shutdown,
)
from launchdarkly_ai_server.tracking import parse_usage
from dotenv import load_dotenv
from utils.logger import log_student, log_debug
import boto3

load_dotenv()

# The legacy SDK emitted these; launchdarkly-ai-server has no feedback API, so
# this module emits them directly. Keep the keys byte-identical or the existing
# feedback metrics in LaunchDarkly stop receiving data.
FEEDBACK_POSITIVE_EVENT = "$ld:ai:feedback:user:positive"
FEEDBACK_NEGATIVE_EVENT = "$ld:ai:feedback:user:negative"


@dataclass
class ServedConfig:
    """One resolved AgentControl config, from LaunchDarkly or from local defaults.

    The current SDK returns plain dicts rather than config objects, and it has no
    `default=` parameter, so the fallback that the SDK used to apply now lives in
    `ConfigManager.get_config`. This wrapper gives the agents one stable surface
    over both sources.
    """

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
        """Custom model params (e.g. max_tool_calls).

        parse_ai_config passes model.custom through untouched, so this keeps
        working the same way the legacy to_dict()['model']['custom'] did.
        """
        return (self.config.get("model") or {}).get("custom") or {}

    @property
    def tools(self) -> dict[str, Any]:
        return self.config.get("tools") or {}

    @property
    def variation_key(self) -> str:
        """The served variation, read from public metadata.

        The legacy code reached into `tracker._variation_key`. The SDK now
        returns this in the variation metadata, so no private access is needed.
        Local fallbacks have no variation, hence 'fallback'.
        """
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

    async def _ensure_client(self):
        """Initialize the shared LaunchDarkly client once.

        init_client is idempotent, so this is safe to await on every request. The
        key is passed explicitly so this app keeps using LD_SDK_KEY.
        """
        await init_client({"sdkKey": self.sdk_key})

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
        """Move a top-level `tools` array to where the live payload keeps it.

        LaunchDarkly serves tools inside `model.parameters.tools` as an array,
        with no top-level `tools` key. ld-aic reads them from there but writes
        them to the top level of `.ai_config_defaults.json`, so the fallback file
        does not match the shape the app actually receives.

        That divergence matters twice. This app reads its tools from
        `model.parameters` (see dynamic_tool_factory and agent_service), so a
        top-level array would leave the agents with no tools whenever the
        fallback is used. And the SDK validates a top-level `tools` key as an
        object, so leaving the array there fails parsing for a key the live
        payload never even sends.

        Moving it makes the fallback behave exactly like a served config.

        Drop this once ld-aic writes tools under model.parameters.
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

        The current SDK has no `default=` parameter, so step 2 is applied here
        rather than inside the SDK. inspect_config never raises and returns
        enabled=False on any failure, which is what makes that check possible.
        """
        log_debug(f"CONFIG MANAGER: Getting config for user_id={user_id}, config_key={config_key}")
        log_debug(f"CONFIG MANAGER: User context: {user_context}")

        await self._ensure_client()

        # Build context using centralized method
        ld_user_context = self.build_context(user_id, user_context)
        log_debug(f"CONFIG MANAGER: Built LaunchDarkly context: {ld_user_context}")

        ai_config_key = config_key or os.getenv('LAUNCHDARKLY_AI_CONFIG_KEY', 'support-agent')
        log_debug(f"CONFIG MANAGER: Using AI config key: {ai_config_key}")

        inspected = await inspect_config(ai_config_key, ld_user_context)

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

    async def invoke(self, served: ServedConfig, context: dict, handler, user_input: str, **kwargs):
        """Run a model call through the SDK so AI metrics are recorded.

        Metrics are attributed to a served variation, so a local fallback has
        nothing to attribute to. In that case the handler is called directly and
        no $ld:ai:* events are emitted.
        """
        if served.from_fallback:
            raw = await handler(
                served.config,
                user_input,
                kwargs.get("tool_handlers"),
                kwargs.get("variables"),
                kwargs.get("history"),
            )
            # Normalized to execute_and_track's shape so callers don't branch.
            return {
                "usage": parse_usage(raw.get("usage") or {}),
                "response": raw.get("output") or "",
                "track_data": served.track_data(),
            }

        return await execute_and_track(
            config_key=served.key,
            config=served.config,
            meta=served.meta,
            user_context=context,
            handler=handler,
            user_input=user_input,
            **kwargs,
        )

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

    def track_cost_metric(self, served: ServedConfig, context, cost, config_key=None, track_data=None):
        """Track cost metric with AI Config metadata for experiment attribution.

        This ensures cost events include trackJsonData so they're properly
        associated with AI Config variations in experiments, matching the
        pattern used by token and feedback tracking.

        Args:
            served: The ServedConfig this cost came from
            context: LaunchDarkly context
            cost: Cost value in dollars
            config_key: Unused; retained so existing call sites keep working.
                        The key now comes from `served`.
            track_data: The track_data returned by a tracked invocation. Preferred
                        when available, because it carries the runId that ties this
                        cost event to the specific generation it came from.
        """
        try:
            client = get_client()
            client.track("ai_cost_per_request", context, track_data or served.track_data(), cost)
            client.flush()

        except Exception as e:
            log_debug(f"COST TRACKING ERROR: {e}")
            # Fallback to basic tracking if metadata extraction fails
            client = get_client()
            client.track("ai_cost_per_request", context, None, cost)
            client.flush()

    def track_feedback(self, served: Optional[ServedConfig], context, thumbs_up: bool) -> bool:
        """Track user feedback with LaunchDarkly.

        launchdarkly-ai-server has no feedback API, so this emits the same events
        the legacy tracker did. The metric data carries the served variation so
        feedback stays attributable to it.
        """
        if not served:
            return False

        try:
            event = FEEDBACK_POSITIVE_EVENT if thumbs_up else FEEDBACK_NEGATIVE_EVENT
            client = get_client()
            client.track(event, context, served.track_data(), 1)
            log_student(f"FEEDBACK TRACKED: {'👍 Positive' if thumbs_up else '👎 Negative'}")
            client.flush()
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
