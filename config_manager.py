#!/usr/bin/env python3
"""
Simplified ConfigManager for LaunchDarkly AI Agent integration
"""
import os
import uuid
import boto3
import ldclient
from dotenv import load_dotenv
from launchdarkly_ai_server import (
    GraphNode,
    get_client,
    init_client,
    inspect_config,
    make_track_data,
    resolve_graph,
)
from utils.logger import log_student, log_debug

load_dotenv()

# The AI SDK has no feedback API, so these are emitted directly. Keep the keys
# byte-identical to the ones the previous SDK sent or the existing feedback
# metrics stop receiving data.
FEEDBACK_EVENTS = {
    True: "$ld:ai:feedback:user:positive",
    False: "$ld:ai:feedback:user:negative",
}


class GraphTracker:
    """Emits the graph events for a hand-rolled walk of a resolved graph.

    graph().invoke() records these itself, but this service walks the graph
    by hand through resolve_graph(), so nothing records them for it. Event
    names and payload fields match what the SDK's own runner sends, so the
    graph and per-config monitoring views pick them up.
    """

    def __init__(self, graph_key: str, context: dict, meta: dict | None = None):
        self._graph_key = graph_key
        self._run_id = str(uuid.uuid4())
        self._context = ldclient.Context.from_dict(context)
        self._data = make_track_data(
            GraphNode(key=graph_key, config={}, meta=meta or {}),
            graph_key,
            self._run_id,
        )
        self._nodes_entered = 0

    def _send(self, event: str, data: dict, value=1):
        try:
            get_client().track(event, self._context, data, value)
        except Exception as e:
            log_debug(f"GRAPH TRACK ERROR ({event}): {e}")

    def _track(self, event: str, value=1, extra: dict | None = None):
        self._send(event, {**self._data, **(extra or {})}, value)

    def _node_data(self, node) -> dict:
        return make_track_data(node, self._graph_key, self._run_id)

    def track_node_invocation(self, node):
        """Record this node as it is entered; the ordered series is the path."""
        log_debug(f"GRAPH: entering node {node.key}")
        node_data = self._node_data(node)
        self._send(
            "$ld:ai:graph:node",
            {**node_data, "nodeKey": node.key, "index": self._nodes_entered},
            1,
        )
        self._nodes_entered += 1

    def track_handoff_success(self, source_key: str, target_key: str):
        self._track("$ld:ai:graph:handoff_success", 1, {"sourceKey": source_key, "targetKey": target_key})

    def track_handoff_failure(self, source_key: str, routing):
        self._track("$ld:ai:graph:handoff_failure", 1, {"sourceKey": source_key, "targetKey": routing})

    def track_tool_call(self, node, tool_name: str):
        self._send("$ld:ai:tool_call", {**self._node_data(node), "toolKey": tool_name})

    def track_invocation_success(self):
        self._track("$ld:ai:graph:invocation_success")

    def track_invocation_failure(self):
        self._track("$ld:ai:graph:invocation_failure")

    def track_node_result(self, node, duration_ms: int, success: bool, usage: dict | None = None):
        """Per-node duration, success or error, and tokens, as invoke() sends them."""
        data = self._node_data(node)
        self._send("$ld:ai:duration:total", data, duration_ms)
        self._send("$ld:ai:generation:success" if success else "$ld:ai:generation:error", data)
        usage = usage or {}
        total = usage.get("input", 0) + usage.get("output", 0)
        if total:
            self._send("$ld:ai:tokens:total", data, total)
            self._send("$ld:ai:tokens:input", data, usage.get("input", 0))
            self._send("$ld:ai:tokens:output", data, usage.get("output", 0))

    def track_latency(self, latency_ms: int):
        self._track("$ld:ai:graph:duration:total", latency_ms)

    def track_total_tokens(self, total: int):
        self._track("$ld:ai:graph:total_tokens", total)


class FixedConfigManager:
    def __init__(self):
        """Initialize LaunchDarkly client and AI client"""
        self.sdk_key = os.getenv('LD_SDK_KEY')
        if not self.sdk_key:
            raise ValueError("LD_SDK_KEY environment variable is required")

        self._initialize_launchdarkly_client()

        # Initialize AWS Bedrock session for SSO authentication
        self._initialize_bedrock_session()

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
    

    async def _ensure_ai_client(self):
        """Hand the existing client to the AI SDK. Idempotent."""
        # client= is keyword-only in effect: a positional argument is read as
        # the options dict, not as a client.
        await init_client(client=self.ld_client)

    async def get_agent_graph(self, user_id: str, graph_key: str, user_context: dict = None):
        """Resolve an agent graph and a tracker for a hand-rolled traversal.

        resolve_graph() returns topology only and records nothing, so the
        tracker is ours. Returns (graph, tracker).
        """
        await self._ensure_ai_client()
        ld_user_context = self.build_context(user_id, user_context)

        graph = await resolve_graph(graph_key, context=ld_user_context)
        raw_graph = self.ld_client.variation(
            graph_key, ldclient.Context.from_dict(ld_user_context), {}
        )
        graph_meta = (raw_graph.get("_ldMeta") or {}) if isinstance(raw_graph, dict) else {}
        return graph, GraphTracker(graph_key, ld_user_context, meta=graph_meta)
    

    def clear_cache(self):
        """No-op, kept because AgentService calls it on startup.

        Nothing is cached here: every graph and config is evaluated against
        LaunchDarkly on each request.
        """
        return None

    def flush(self):
        """Flush metrics and clear SDK cache"""
        self.ld_client.flush()

    async def track_feedback(
        self,
        context,
        config_key: str,
        thumbs_up: bool,
        variation_key: str | None = None,
        version: int | None = None,
    ):
        """Track user feedback with LaunchDarkly, attributed to the served variation.

        Prefers the variationKey and version returned with the response so feedback
        never re-evaluates targeting later; falls back to inspect_config only when
        the caller omitted the served variation, and fails if none can be resolved.
        """
        try:
            await self._ensure_ai_client()
            resolved_variation = (variation_key or "").strip()
            resolved_version = version
            if not resolved_variation:
                meta = (await inspect_config(config_key, context))["meta"] or {}
                resolved_variation = (meta.get("variationKey") or "").strip()
                if resolved_version is None:
                    resolved_version = meta.get("version", 1)
            if not resolved_variation:
                log_debug(f"FEEDBACK TRACKING ERROR: no served variationKey for '{config_key}'")
                return False

            data = {
                "configKey": config_key,
                "variationKey": resolved_variation,
                "version": resolved_version if resolved_version is not None else 1,
            }
            ld_context = ldclient.Context.from_dict(context)
            self.ld_client.track(FEEDBACK_EVENTS[bool(thumbs_up)], ld_context, data, 1)
            log_student(f"FEEDBACK TRACKED: {'👍 Positive' if thumbs_up else '👎 Negative'} ({resolved_variation})")
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