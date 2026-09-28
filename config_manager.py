#!/usr/bin/env python3
"""
Simplified ConfigManager for LaunchDarkly AI Agent integration
"""
import os
import json
from pathlib import Path
import asyncio
import ldclient
from launchdarkly_ai_server import (
    get_client,
    init_client,
    inspect_config,
    parse_ai_config,
    resolve_graph,
)

# The AI SDK has no feedback API, so these are emitted directly. Keep the keys
# byte-identical to the ones the previous SDK sent or the existing feedback
# metrics stop receiving data.
FEEDBACK_EVENTS = {
    True: "$ld:ai:feedback:user:positive",
    False: "$ld:ai:feedback:user:negative",
}


class GraphTracker:
    """Emits the graph events that the SDK used to emit for a hand-rolled walk.

    graph().invoke() records these itself, but this service traverses the graph
    by hand through resolve_graph(), so nothing records them for it. The method
    names match what agent_service already calls.

    The event keys are the CURRENT ones, which differ from the previous SDK:

        $ld:ai:graph:handoff      -> handoff_success / handoff_failure
        $ld:ai:graph:invocation   -> invocation_success / invocation_failure
        $ld:ai:graph:total        -> total_tokens
        $ld:ai:tool               -> tool_call
        $ld:ai:graph:path         -> graph:node, one event per node entered

    Any LaunchDarkly metric keyed on the old names needs recreating against the
    new ones. There is no replacement for the old graph:redirect event.
    """

    def __init__(self, graph_key: str, context: dict):
        self._graph_key = graph_key
        self._context = context
        self._data = {"graphKey": graph_key}
        self._nodes_entered = 0

    def _track(self, event: str, value=1, extra: dict | None = None):
        try:
            data = {**self._data, **extra} if extra else self._data
            get_client().track(event, self._context, data, value)
        except Exception as e:
            log_debug(f"GRAPH TRACK ERROR ({event}): {e}")

    def track_node_invocation(self, node_key: str):
        """Record this node as it is entered.

        0.2.4 added $ld:ai:graph:node for exactly this, and the ordered series
        of these events is the path the walk took. Emitted on entry rather than
        at the end so a node that then fails still leaves its step behind.
        """
        log_debug(f"GRAPH: entering node {node_key}")
        self._track(
            "$ld:ai:graph:node", 1, {"nodeKey": node_key, "index": self._nodes_entered}
        )
        self._nodes_entered += 1

    def track_handoff_success(self, source_key: str, target_key: str):
        self._track("$ld:ai:graph:handoff_success")

    def track_handoff_failure(self, source_key: str, routing):
        self._track("$ld:ai:graph:handoff_failure")

    def track_tool_call(self, node_key: str, tool_name: str):
        self._track("$ld:ai:tool_call")

    def track_invocation_success(self):
        self._track("$ld:ai:graph:invocation_success")

    def track_invocation_failure(self):
        self._track("$ld:ai:graph:invocation_failure")

    def track_node_success(self, node_key: str, config: dict):
        self._track_generation("$ld:ai:generation:success", node_key, config, 1)

    def track_node_error(self, node_key: str, config: dict):
        self._track_generation("$ld:ai:generation:error", node_key, config, 1)

    def _track_generation(self, event: str, node_key: str, config: dict, value):
        model = (config or {}).get("model") or {}
        data = {
            "graphKey": self._graph_key,
            "configKey": node_key,
            "modelName": model.get("name", "unknown"),
            "providerName": ((config or {}).get("provider") or {}).get("name", "unknown"),
        }
        try:
            get_client().track(event, self._context, data, value)
        except Exception as e:
            log_debug(f"GRAPH TRACK ERROR ({event}): {e}")

    def track_latency(self, latency_ms: int):
        self._track("$ld:ai:graph:duration:total", latency_ms)

    def track_node_duration(self, node_key: str, config: dict, duration_ms: int):
        """Record one node's generation duration.

        The caller used to build this event by reaching into the tracker's
        _ld_client and _context and reading five private attributes off the
        node's config tracker. Configs are plain dicts now, so the model and
        provider come from public keys instead.
        """
        model = (config or {}).get("model") or {}
        data = {
            "graphKey": self._graph_key,
            "configKey": node_key,
            "modelName": model.get("name", "unknown"),
            "providerName": ((config or {}).get("provider") or {}).get("name", "unknown"),
        }
        try:
            get_client().track("$ld:ai:duration:total", self._context, data, duration_ms)
        except Exception as e:
            log_debug(f"GRAPH TRACK ERROR (duration): {e}")

    def track_total_tokens(self, total: int):
        """Total tokens across the walk.

        Takes an int. The previous tracker took a TokenUsage object; this event
        carries a single numeric value.
        """
        self._track("$ld:ai:graph:total_tokens", total)

    def track_path(self, path):
        """No-op. The path is the series of $ld:ai:graph:node events.

        Kept so the caller does not need to change; 0.2.4 retired the single
        $ld:ai:graph:path event that this used to send.
        """
        log_debug(f"GRAPH: path {' -> '.join(path)}")
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

    def _get_default_config(self, config_key: str) -> dict:
        """Get fallback config from .ai_config_defaults.json

        Args:
            config_key: The AI config key (e.g., 'support-agent')

        Returns:
            A dict in the shape the SDK serves, validated by parse_ai_config

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

        # Configs are plain dicts now, so this shape is what the SDK serves
        # rather than an AIAgentConfigDefault. Tools are managed by
        # LaunchDarkly and not part of defaults.
        candidate = {
            "model": {
                "name": config_data["model"]["name"],
                "parameters": config_data["model"].get("parameters", {}),
            },
            "provider": {"name": config_data["provider"]["name"]},
            "instructions": config_data.get("instructions", "You are a helpful assistant."),
        }

        # Validated rather than trusted: a stale defaults file should fail
        # loudly here instead of being served to a model.
        result = parse_ai_config(candidate)
        if not result.success:
            raise ValueError(
                f"Fallback config '{config_key}' in .ai_config_defaults.json is not valid: "
                f"{result.error.get('message')}\n\nRegenerate it with:\n"
                "  python bootstrap/create_configs.py"
            )
        return result.data
    
    def _initialize_launchdarkly_client(self):
        """Initialize LaunchDarkly client and hand it to the AI SDK"""
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

        # There is no separate AI client to build. init_client is a coroutine,
        # so this client is handed over on first use in _ensure_ai_client.

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

    def build_context(self, user_id: str, user_context: dict = None) -> dict:
        """Build a LaunchDarkly context with consistent attributes.

        This ensures the same context is used for AI Config evaluation
        and standard tracking.
        """
        # Contexts are plain dicts now; there is no builder.
        context = {"kind": "user", "key": user_id}

        if user_context:
            # Set all attributes from user_context for consistency
            for key, value in user_context.items():
                context[key] = value
                log_debug(f"CONFIG MANAGER: Set {key}={value}")

        return context
    

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

        await self._ensure_ai_client()

        # There is no `default=` parameter on this SDK, so the fallback is
        # applied here. inspect_config never raises and reports enabled=False
        # on any failure, which keeps this to one branch.
        inspected = await inspect_config(ai_config_key, ld_user_context)

        if inspected["enabled"] and inspected["config"]:
            config = inspected["config"]
            meta = inspected["meta"] or {}
            log_debug("CONFIG MANAGER: ✅ Got config from LaunchDarkly")
            log_debug(f"CONFIG MANAGER: Model: {(config.get('model') or {}).get('name', 'unknown')}")
            # The variation key is public metadata now, not a private tracker
            # attribute read behind a hasattr guard.
            log_debug(f"CONFIG MANAGER: Variation: {meta.get('variationKey', 'unknown')}")
            return config

        log_student(f"CONFIG MANAGER: '{ai_config_key}' not served, using .ai_config_defaults.json")
        return self._get_default_config(ai_config_key)

    async def _ensure_ai_client(self):
        """Hand the existing client to the AI SDK. Idempotent."""
        # client= is keyword-only in effect: a positional argument is read as
        # the options dict, not as a client.
        await init_client(client=self.ld_client)

    async def get_agent_graph(self, user_id: str, graph_key: str, user_context: dict = None):
        """Resolve an agent graph and a tracker for a hand-rolled traversal.

        This method did not exist: agent_service called it but nothing defined
        it, so the graph path raised AttributeError before any of this ran. It
        is written here against resolve_graph(), which the SDK documents as the
        path "for framework-native runners" -- i.e. callers that walk the graph
        themselves, which is what agent_service does.

        resolve_graph returns topology only and records nothing, so the tracker
        is ours. Returns (graph, tracker); the graph exposes `enabled`, `root`,
        `edges_from`, and `reverse_traverse` as attributes.
        """
        await self._ensure_ai_client()
        ld_user_context = self.build_context(user_id, user_context)

        graph = await resolve_graph(graph_key, context=ld_user_context)
        return graph, GraphTracker(graph_key, ld_user_context)
    

    def flush(self):
        """Flush metrics and clear SDK cache"""
        self.ld_client.flush()

    def track_feedback(self, context, thumbs_up: bool):
        """Track user feedback with LaunchDarkly.

        There is no tracker and no feedback API, so this emits the legacy event
        directly. `context` replaces the tracker argument, because the event
        has to land on the same context the config was evaluated with.
        """
        try:
            self.ld_client.track(FEEDBACK_EVENTS[bool(thumbs_up)], context, None, 1)
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