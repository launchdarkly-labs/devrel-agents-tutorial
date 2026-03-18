"""
Agent Graph Executor - TRUE DYNAMIC execution of LaunchDarkly Agent Graphs.

No agent registry. No custom state handling. Just:
1. Fetch graph from LaunchDarkly
2. Traverse nodes by following edges
3. Each node uses generic agent with its AI Config
4. Tools loaded dynamically from config

Add/remove any agent in LaunchDarkly - it just works.
"""
import os
import time
import uuid
from typing import Dict, Any
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
from ldai.tracker import TokenUsage
from ..models import ChatResponse, AgentConfig as APIAgentConfig
from config_manager import FixedConfigManager as ConfigManager
from utils.logger import log_student
from agents.generic_agent import create_generic_agent

load_dotenv()

MAX_HOPS = 10  # Safety limit


class AgentGraphExecutor:
    """
    Fully dynamic Agent Graph executor.

    - No agent registry
    - No custom state handling per agent type
    - All behavior driven by LaunchDarkly AI Config
    """

    def __init__(self, config_manager: ConfigManager) -> None:
        self.config_manager = config_manager

    async def execute_with_graph(
        self,
        graph_key: str,
        user_id: str,
        user_input: str,
        user_context: dict = None,
        sanitized_history: list = None
    ) -> Dict[str, Any]:
        """Execute agents by traversing the LaunchDarkly Agent Graph."""
        graph = self.config_manager.get_agent_graph(user_id, graph_key, user_context)

        if not graph.is_enabled():
            raise ValueError(f"Agent Graph '{graph_key}' is not enabled")

        # Shared context - generic, no agent-specific fields
        ctx = {
            "user_id": user_id,
            "user_input": user_input,
            "user_context": user_context or {},
            "messages": [HumanMessage(content=user_input)],
            "processed_input": user_input,
            "final_response": "",
            "tool_calls": [],
            "agent_configs": [],
            "total_input_tokens": 0,
            "total_output_tokens": 0,
        }

        graph_tracker = graph.get_tracker()
        graph_start_time = time.time()
        execution_path = []

        # Build node lookup
        nodes = {}
        graph.reverse_traverse(lambda node, _: nodes.update({node.get_key(): node}), {})
        log_student(f"GRAPH: '{graph_key}' with {len(nodes)} nodes: {list(nodes.keys())}")

        try:
            current_node = graph.root()
            if not current_node:
                raise ValueError("Agent graph has no root node")

            prev_node_key = None
            visited = set()
            hop_count = 0

            # Traverse until terminal node
            while current_node:
                node_key = current_node.get_key()

                # Safety checks
                if node_key in visited:
                    raise ValueError(f"Cycle detected at: {node_key}")
                visited.add(node_key)
                hop_count += 1
                if hop_count > MAX_HOPS:
                    raise ValueError(f"Max hops exceeded: {hop_count}")

                config = current_node.get_config()
                execution_path.append(node_key)

                # Track
                if graph_tracker:
                    graph_tracker.track_node_invocation(node_key)
                    if prev_node_key:
                        graph_tracker.track_handoff_success(prev_node_key, node_key)

                # Get valid routes from outgoing edges
                edges = current_node.get_edges()
                valid_routes = []
                for edge in edges:
                    handoff = edge.handoff or {}
                    route = handoff.get("route")
                    if route:
                        valid_routes.append(route)

                # Execute with generic agent, passing valid routes
                log_student(f"EXECUTING: {node_key}")
                node_start = time.time()

                agent = create_generic_agent(config, self.config_manager, valid_routes=valid_routes)
                result = await agent.ainvoke(ctx)

                duration_ms = int((time.time() - node_start) * 1000)
                self._track_duration(graph_tracker, graph_key, config, duration_ms)

                # Update context with results (generic)
                self._update_context(node_key, config, result, ctx)

                # Find next node (edges already fetched above)
                if not edges:
                    log_student(f"TERMINAL: {node_key}")
                    break

                next_node = self._select_next_node(edges, result, nodes)
                prev_node_key = node_key
                current_node = next_node

            # Track graph metrics
            self._track_graph_metrics(graph_tracker, ctx, execution_path, graph_start_time)
            log_student(f"PATH: {' → '.join(execution_path)}")

        except Exception as e:
            log_student(f"GRAPH ERROR: {e}")
            if graph_tracker:
                graph_tracker.track_invocation_failure()
            raise

        return ctx

    def _select_next_node(self, edges, result: dict, nodes: dict):
        """Select next node based on agent result and edge handoffs."""
        routing = result.get("routing_decision", "").lower() if result.get("routing_decision") else None

        # Log available edges
        for edge in edges:
            handoff = edge.handoff or {}
            route = handoff.get("route", "").lower()
            log_student(f"  EDGE: → {edge.target_config} (route={route})")

        # If we have an explicit routing decision, match it to edge route
        if routing:
            for edge in edges:
                handoff = edge.handoff or {}
                route = handoff.get("route", "").lower()

                # Exact match or contains match
                if route == routing or routing in route or route in routing:
                    log_student(f"  MATCHED: routing='{routing}' → route='{route}' → {edge.target_config}")
                    return nodes.get(edge.target_config)

        # Default: first edge
        if edges:
            default = edges[0].target_config
            log_student(f"  DEFAULT: → {default}")
            return nodes.get(default)

        return None

    def _update_context(self, node_key: str, config, result: dict, ctx: dict):
        """Update context with agent results - fully generic."""
        # Aggregate tokens
        if "_token_usage" in result:
            ctx["total_input_tokens"] += result["_token_usage"].get("input", 0)
            ctx["total_output_tokens"] += result["_token_usage"].get("output", 0)

        # Always update final response and tool calls from latest agent
        if "response" in result:
            ctx["final_response"] = result["response"]
            ctx["processed_input"] = result.get("response", ctx["processed_input"])

        if "tool_calls" in result:
            ctx["tool_calls"] = result["tool_calls"]

        # Get variation key
        var_key = "default"
        if hasattr(config, 'tracker') and hasattr(config.tracker, '_variation_key'):
            var_key = config.tracker._variation_key

        # Record agent config - fully generic, include all result fields
        agent_info = {
            "agent_name": node_key,
            "variation_key": var_key,
            "model": config.model.name if hasattr(config, 'model') else "unknown",
            "tools_used": result.get("tool_calls", []),
        }

        # Include all non-internal fields from result
        for key, value in result.items():
            if not key.startswith("_") and key not in ["response", "tool_calls"]:
                agent_info[key] = value

        ctx["agent_configs"].append(agent_info)

    def _track_duration(self, graph_tracker, graph_key: str, config, duration_ms: int):
        """Track node duration."""
        if not graph_tracker or not config:
            return
        if not hasattr(graph_tracker, '_ld_client'):
            return

        tracker = config.tracker
        track_data = {
            'graphKey': graph_key,
            'configKey': getattr(tracker, '_config_key', 'unknown'),
            'variationKey': getattr(tracker, '_variation_key', 'default'),
            'version': getattr(tracker, '_version', 1),
            'modelName': getattr(tracker, '_model_name', 'unknown'),
            'providerName': getattr(tracker, '_provider_name', 'unknown'),
        }
        graph_tracker._ld_client.track(
            "$ld:ai:duration:total",
            graph_tracker._context,
            track_data,
            duration_ms
        )

    def _track_graph_metrics(self, graph_tracker, ctx: dict, path: list, start_time: float):
        """Track overall graph metrics."""
        if not graph_tracker:
            return

        graph_tracker.track_path(path)
        latency_ms = int((time.time() - start_time) * 1000)
        graph_tracker.track_latency(latency_ms)
        log_student(f"LATENCY: {latency_ms}ms")

        total_in = ctx.get("total_input_tokens", 0)
        total_out = ctx.get("total_output_tokens", 0)
        if total_in > 0 or total_out > 0:
            graph_tracker.track_total_tokens(
                TokenUsage(input=total_in, output=total_out, total=total_in + total_out)
            )

        graph_tracker.track_invocation_success()


class AgentService:
    """Multi-Agent Orchestration using LaunchDarkly Agent Graph."""

    def __init__(self):
        self.config_manager = ConfigManager()
        self.config_manager.clear_cache()
        self.graph_executor = AgentGraphExecutor(self.config_manager)

    def flush_metrics(self):
        self.config_manager.close()

    async def process_message(
        self,
        user_id: str,
        message: str,
        user_context: dict = None,
        sanitized_conversation_history: list = None
    ) -> ChatResponse:
        """Process message using LaunchDarkly Agent Graph."""
        try:
            if not message or not message.strip():
                return self._error_response("Please provide a message.")

            result = await self.graph_executor.execute_with_graph(
                graph_key=os.getenv("AGENT_GRAPH_KEY", "chatbot-flow"),
                user_id=user_id.strip() or "anonymous",
                user_input=message,
                user_context=user_context or {}
            )

            return ChatResponse(
                id=str(uuid.uuid4()),
                response=result.get("final_response", ""),
                tool_calls=result.get("tool_calls", []),
                variation_key="agent-graph",
                model="multi-agent",
                agent_configurations=[
                    APIAgentConfig(
                        agent_name=cfg["agent_name"],
                        variation_key=cfg.get("variation_key", "default"),
                        model=cfg.get("model", "unknown"),
                        tools=cfg.get("tools", []),
                        tools_used=cfg.get("tools_used", []),
                        detected=cfg.get("detected"),
                        types=cfg.get("types"),
                        redacted=cfg.get("redacted")
                    )
                    for cfg in result.get("agent_configs", [])
                ]
            )

        except Exception as e:
            log_student(f"ERROR: {e}")
            return self._error_response(f"Error: {e}")

    def _error_response(self, message: str) -> ChatResponse:
        return ChatResponse(
            id=str(uuid.uuid4()),
            response=message,
            tool_calls=[],
            variation_key="error",
            model="error",
            agent_configurations=[]
        )
