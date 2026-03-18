"""
Generic Agent - TRUE DYNAMIC agent that works with any LaunchDarkly AI Config.

No hardcoded agent types. No assumptions. Everything from LaunchDarkly:
- Instructions from AI Config
- Tools from AI Config
- Valid routes from Graph edges
"""
from typing import List, Optional
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from utils.logger import log_student


def create_generic_agent(agent_config, config_manager, valid_routes: List[str] = None):
    """
    Create a generic agent from LaunchDarkly AI Config.

    Args:
        agent_config: LaunchDarkly AI Config
        config_manager: Config manager for model creation
        valid_routes: List of valid route values from outgoing edges (e.g., ["security", "support"])
    """
    from agents.ld_agent_helpers import (
        create_model_for_config, _rate_limit_llm_call,
        wrap_tool_with_counter, ToolCallCounter
    )
    from tools_impl.dynamic_tool_factory import create_dynamic_tools_from_launchdarkly
    from ldai.tracker import TokenUsage
    import time

    class GenericAgent:
        def __init__(self):
            self.tools = []
            self.has_tools = False
            self.valid_routes = valid_routes or []

        async def ainvoke(self, state: dict) -> dict:
            """Execute the agent using LaunchDarkly config."""

            if not agent_config.enabled:
                log_student(f"AGENT DISABLED: skipping")
                return {"response": "", "_skipped": True}

            try:
                # Create model from config
                model = create_model_for_config(
                    provider=agent_config.provider.name,
                    model=agent_config.model.name,
                    config_manager=config_manager,
                    temperature=0.3
                )

                log_student(f"CONFIG: {agent_config.provider.name} - {agent_config.model.name}")

                # Load tools from LaunchDarkly config
                self.tools = create_dynamic_tools_from_launchdarkly(agent_config)
                self.has_tools = len(self.tools) > 0

                if self.has_tools:
                    log_student(f"TOOLS: {[t.name for t in self.tools]}")

                # Get instructions from config
                instructions = agent_config.instructions or "Process the input and provide a helpful response."

                # If this node has outgoing edges with routes, inject route options into instructions
                if self.valid_routes:
                    route_instruction = f"\n\nYou must select one of these routes: {self.valid_routes}. Return your choice in this exact JSON format at the end of your response: {{\"route\": \"<selected_route>\"}}"
                    instructions = instructions + route_instruction
                    log_student(f"ROUTES AVAILABLE: {self.valid_routes}")

                # Get input
                user_input = state.get("processed_input", state.get("user_input", ""))
                messages = state.get("messages", [HumanMessage(content=user_input)])

                _rate_limit_llm_call()
                start_time = time.time()

                # Execute based on whether we have tools
                if self.has_tools:
                    result = await self._execute_with_tools(model, instructions, messages)
                else:
                    result = await self._execute_simple(model, instructions, messages)

                # Track metrics
                duration_ms = int((time.time() - start_time) * 1000)
                agent_config.tracker.track_duration(duration_ms)
                agent_config.tracker.track_success()

                log_student(f"DURATION: {duration_ms}ms")

                if "_token_usage" in result and result["_token_usage"]["total"] > 0:
                    agent_config.tracker.track_tokens(TokenUsage(**result["_token_usage"]))

                return result

            except Exception as e:
                log_student(f"AGENT ERROR: {e}")
                agent_config.tracker.track_error()
                return {
                    "response": f"Error: {e}",
                    "_error": str(e)
                }

        async def _execute_with_tools(self, model, instructions: str, messages: list) -> dict:
            """Execute using ReAct agent with tools."""
            from langgraph.prebuilt import create_react_agent

            # Get max_tool_calls from config
            max_tool_calls = 20  # Default higher for tool-using agents
            try:
                config_dict = agent_config.to_dict()
                # Try multiple possible paths for custom parameters
                custom = config_dict.get('model', {}).get('custom', {}) or {}
                if not custom:
                    custom = config_dict.get('model', {}).get('parameters', {}).get('custom', {}) or {}
                if 'max_tool_calls' in custom:
                    max_tool_calls = int(custom['max_tool_calls'])
                    log_student(f"CONFIG: max_tool_calls={max_tool_calls} from LaunchDarkly")
            except Exception as e:
                log_student(f"CONFIG: using default max_tool_calls={max_tool_calls}")

            # Wrap tools with counter for logging
            counter = ToolCallCounter(max_calls=max_tool_calls)
            wrapped_tools = [wrap_tool_with_counter(t, counter) for t in self.tools]
            recursion_limit = max_tool_calls * 3 + 10

            agent = create_react_agent(
                model=model,
                tools=wrapped_tools,
                prompt=instructions
            )

            result = await agent.ainvoke({"messages": messages}, {"recursion_limit": recursion_limit})

            # Extract response and tool calls
            response_text = ""
            tool_calls = []
            token_usage = {"input": 0, "output": 0, "total": 0}

            for msg in result.get("messages", []):
                if isinstance(msg, AIMessage):
                    if msg.content:
                        response_text = msg.content
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        for tc in msg.tool_calls:
                            # Handle both dict and object access
                            tool_name = tc.get('name') if isinstance(tc, dict) else getattr(tc, 'name', None)
                            if tool_name and tool_name not in tool_calls:
                                tool_calls.append(tool_name)
                    if hasattr(msg, 'usage_metadata') and msg.usage_metadata:
                        token_usage = {
                            "input": msg.usage_metadata.get("input_tokens", 0),
                            "output": msg.usage_metadata.get("output_tokens", 0),
                            "total": msg.usage_metadata.get("total_tokens", 0)
                        }

            # Extract route if present
            route = self._extract_route(response_text)

            return {
                "response": response_text,
                "routing_decision": route,
                "tool_calls": tool_calls,
                "_token_usage": token_usage
            }

        async def _execute_simple(self, model, instructions: str, messages: list) -> dict:
            """Execute simple LLM call without tools."""

            full_messages = [SystemMessage(content=instructions)] + messages
            response = await model.ainvoke(full_messages)

            response_text = response.content if hasattr(response, 'content') else str(response)

            # Extract token usage
            token_usage = {"input": 0, "output": 0, "total": 0}
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                token_usage = {
                    "input": response.usage_metadata.get("input_tokens", 0),
                    "output": response.usage_metadata.get("output_tokens", 0),
                    "total": response.usage_metadata.get("total_tokens", 0)
                }

            # Extract route if present
            route = self._extract_route(response_text)
            if route:
                log_student(f"ROUTE SELECTED: {route}")

            return {
                "response": response_text,
                "routing_decision": route,
                "tool_calls": [],
                "_token_usage": token_usage
            }

        def _extract_route(self, response_text: str) -> Optional[str]:
            """Extract route from response JSON with strict validation."""
            import json
            import re

            # Try to find JSON object with route key
            json_patterns = [
                r'```json\s*(\{[^`]+\})\s*```',  # Fenced code block
                r'(\{"route":\s*"[^"]+"\s*\})',   # Inline JSON
                r'(\{[^{}]*"route"\s*:\s*"[^"]+[^{}]*\})',  # Relaxed JSON
            ]

            for pattern in json_patterns:
                match = re.search(pattern, response_text, re.DOTALL)
                if match:
                    try:
                        data = json.loads(match.group(1))
                        route = data.get("route", "").lower().strip()

                        # Exact match validation against valid routes
                        if self.valid_routes:
                            valid_lower = [r.lower() for r in self.valid_routes]
                            if route in valid_lower:
                                # Return the original casing from valid_routes
                                idx = valid_lower.index(route)
                                return self.valid_routes[idx]
                            else:
                                log_student(f"INVALID ROUTE: '{route}' not in {self.valid_routes}")
                                return None
                        return route
                    except json.JSONDecodeError:
                        continue

            return None

    return GenericAgent()
