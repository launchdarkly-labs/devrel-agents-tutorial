"""
Generic Agent - TRUE DYNAMIC agent that works with any LaunchDarkly AI Config.

No hardcoded agent types. No registry. Just:
1. Read instructions from config
2. Load tools from config
3. Execute and return response

Add any node to your Agent Graph - this agent handles it.
"""
from typing import Dict, Any, Optional
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent
from utils.logger import log_student


def create_generic_agent(agent_config, config_manager):
    """
    Create a generic agent from any LaunchDarkly AI Config.

    The config provides everything:
    - instructions: system prompt
    - model: which LLM to use
    - tools: what capabilities to bind

    Returns an agent that can handle any workflow node.
    """
    from agents.ld_agent_helpers import (
        create_model_for_config, _rate_limit_llm_call, extract_token_usage
    )
    from tools_impl.dynamic_tool_factory import create_dynamic_tools_from_launchdarkly
    from ldai.tracker import TokenUsage
    import time

    class GenericAgent:
        def __init__(self):
            self.tools = []
            self.has_tools = False

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

                log_student(f"AGENT CONFIG: {agent_config.provider.name} - {agent_config.model.name}")

                # Load tools from LaunchDarkly config
                self.tools = create_dynamic_tools_from_launchdarkly(agent_config)
                self.has_tools = len(self.tools) > 0

                if self.has_tools:
                    log_student(f"TOOLS LOADED: {[t.name for t in self.tools]}")

                # Get instructions from config
                instructions = agent_config.instructions or "Process the input and provide a helpful response."

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

                log_student(f"AGENT: duration={duration_ms}ms")

                if "_token_usage" in result and result["_token_usage"]["total"] > 0:
                    agent_config.tracker.track_tokens(TokenUsage(**result["_token_usage"]))
                    log_student(f"AGENT TOKENS: {result['_token_usage']['total']} ({result['_token_usage']['input']} in, {result['_token_usage']['output']} out)")

                return result

            except Exception as e:
                log_student(f"AGENT ERROR: {e}")
                agent_config.tracker.track_error()
                return {
                    "response": f"Error processing request: {e}",
                    "_error": str(e)
                }

        async def _execute_with_tools(self, model, instructions: str, messages: list) -> dict:
            """Execute using ReAct agent with tools."""
            from langgraph.prebuilt import create_react_agent

            # Create ReAct agent with tools
            agent = create_react_agent(
                model=model,
                tools=self.tools,
                prompt=instructions
            )

            # Run agent
            result = await agent.ainvoke({"messages": messages})

            # Extract response and tool calls
            response_text = ""
            tool_calls = []
            token_usage = {"input": 0, "output": 0, "total": 0}

            for msg in result.get("messages", []):
                if isinstance(msg, AIMessage):
                    if msg.content:
                        response_text = msg.content
                    # Track tool calls
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        for tc in msg.tool_calls:
                            tool_name = tc.get('name', 'unknown')
                            if tool_name not in tool_calls:
                                tool_calls.append(tool_name)
                    # Extract token usage
                    if hasattr(msg, 'usage_metadata') and msg.usage_metadata:
                        token_usage = {
                            "input": msg.usage_metadata.get("input_tokens", 0),
                            "output": msg.usage_metadata.get("output_tokens", 0),
                            "total": msg.usage_metadata.get("total_tokens", 0)
                        }

            return {
                "response": response_text,
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

            # Parse routing decision if present in response
            routing_decision = self._extract_routing(response_text)

            result = {
                "response": response_text,
                "tool_calls": [],
                "_token_usage": token_usage
            }

            if routing_decision:
                result["routing_decision"] = routing_decision

            return result

        def _extract_routing(self, response_text: str) -> Optional[str]:
            """Extract routing decision from response if present."""
            text_lower = response_text.lower()

            # Look for routing keywords
            if "security" in text_lower or "pii" in text_lower:
                return "security"
            elif "support" in text_lower:
                return "support"

            return None

    return GenericAgent()
