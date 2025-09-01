from __future__ import annotations

import asyncio
import json
import logging
import os
import reprlib
import uuid
import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import TypedDict, List, Annotated, Optional, Any, Dict
from datetime import datetime, timedelta
from urllib.parse import urlparse

try:
    from cachetools import TTLCache
except ImportError:
    # Fallback simple cache if cachetools not available
    class TTLCache(dict):
        def __init__(self, maxsize, ttl):
            super().__init__()
            self.maxsize = maxsize
            self.ttl = ttl
            self._timestamps = {}
        
        def __getitem__(self, key):
            if key in self._timestamps:
                if time.time() - self._timestamps[key] > self.ttl:
                    del self[key]
                    del self._timestamps[key]
                    raise KeyError(key)
            return super().__getitem__(key)
        
        def __setitem__(self, key, value):
            if len(self) >= self.maxsize and key not in self:
                # Simple eviction - remove oldest
                oldest_key = min(self._timestamps.keys(), key=lambda k: self._timestamps[k])
                del self[oldest_key]
                del self._timestamps[oldest_key]
            super().__setitem__(key, value)
            self._timestamps[key] = time.time()

from langgraph.graph import StateGraph, add_messages
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    ToolMessage,
    BaseMessage,
    SystemMessage,
)
from langchain_core.tools import BaseTool

from tools_impl.search_v1 import SearchToolV1
from tools_impl.search_v2 import SearchToolV2
from tools_impl.reranking import RerankingTool
from policy.config_manager import AgentConfig, ConfigManager


# ========= Logging (hardened) =========
logger = logging.getLogger("ld.agent")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s]: %(message)s", datefmt="%H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Respect env override; default INFO
_env_level = os.getenv("LD_AGENT_LOG_LEVEL")
if _env_level:
    try:
        logger.setLevel(getattr(logging, _env_level.upper()))
    except Exception:
        logger.setLevel(logging.INFO)
else:
    logger.setLevel(logging.INFO)

# Compact repr for any optional debug dumps
_preview = reprlib.Repr()
_preview.maxstring = 200
_preview.maxother = 200

# ========= Global MCP Throttling State =========
_semantic_scholar_hostnames = {"api.semanticscholar.org", "www.semanticscholar.org"}
_host_backoff_until: Dict[str, datetime] = {}
_host_lock = threading.Lock()
_concurrency = threading.Semaphore(4)  # Global concurrency gate
_tool_result_cache = TTLCache(maxsize=512, ttl=90)  # 90s TTL cache for duplicate queries


def _run_id() -> str:
    return uuid.uuid4().hex[:8]


# ========= Behavior Defaults (can be overridden via AgentConfig.knobs) =========
FINAL_SENTINEL_DEFAULT = "<FINAL/>"
MAX_TOOL_CALLS_DEFAULT = 8
TARGET_MIN_TOOL_CALLS_DEFAULT = 5
MAX_ASSISTANT_TURNS_DEFAULT = 10
SYNTHESIS_PATIENCE_DEFAULT = 2

MODEL_TIMEOUT_S_DEFAULT = 60
MODEL_MAX_RETRIES_DEFAULT = 2

TOOL_TIMEOUT_S_DEFAULT = 45
TOOL_MAX_RETRIES_DEFAULT = 1
PARALLEL_TOOLS_DEFAULT = True
MAX_PARALLEL_DEFAULT = 4
TRUNCATE_TOOL_RESULT_DEFAULT = 4000
MAX_TOOL_MESSAGES_KEPT_DEFAULT = 6


# ========= Agent State =========
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    user_input: str
    response: str
    tool_calls: List[str]
    tool_details: List[dict]
    most_recent_search_results: Optional[str]
    most_recent_query: Optional[str]
    run_id: Optional[str]


# ========= Helpers (generic) =========
def _norm_args(args: dict) -> str:
    """Normalize args for duplicate guidance (stable subset, lowercased strings)."""
    if not isinstance(args, dict):
        return ""
    keep = {k: args.get(k) for k in (
        "query","search_query","q","text",
        "top_k","filter",
        # common arXiv / S2 keys to distinguish similar calls
        "categories","date_from","max_results","year","limit","offset","sort"
    )}
    for k in list(keep.keys()):
        v = keep[k]
        if v is None:
            keep.pop(k, None)
        elif isinstance(v, str):
            keep[k] = v.strip().lower()
    try:
        return json.dumps(keep, sort_keys=True, ensure_ascii=False)
    except Exception:
        return str(keep)


def _collect_tool_history(messages: List[BaseMessage], limit: int = 12):
    """Return last up-to-`limit` unique calls by (tool_name, normalized_args), most-recent last."""
    calls = []
    for m in messages:
        for tc in getattr(m, "tool_calls", []) or []:
            name = tc.get("name", "unknown")
            args = tc.get("args", {}) or {}
            calls.append((name, _norm_args(args)))
    seen = set()
    uniq = []
    for name, sig in reversed(calls):
        key = (name, sig)
        if key in seen:
            continue
        seen.add(key)
        uniq.append((name, sig))
        if len(uniq) >= limit:
            break
    return list(reversed(uniq))


def _consecutive_ai_without_tools(msgs: List[BaseMessage]) -> int:
    n = 0
    for m in reversed(msgs):
        if isinstance(m, ToolMessage) or isinstance(m, HumanMessage):
            break
        if isinstance(m, AIMessage):
            if getattr(m, "tool_calls", None):
                break
            n += 1
    return n


def _truncate_text(s: Any, limit: int) -> str:
    s = s if isinstance(s, str) else str(s)
    if len(s) <= limit:
        return s
    return s[:limit] + f"\n...[truncated {len(s)-limit} chars]"


def _prune_messages(msgs: List[BaseMessage], max_tool_msgs_kept: int) -> List[BaseMessage]:
    """Keep only the last N ToolMessages to limit context growth (index-based; no hashing)."""
    tool_indices = [i for i, m in enumerate(msgs) if isinstance(m, ToolMessage)]
    if len(tool_indices) <= max_tool_msgs_kept:
        return msgs
    keep_indices = set(tool_indices[-max_tool_msgs_kept:])
    pruned = [m for i, m in enumerate(msgs) if not (isinstance(m, ToolMessage) and i not in keep_indices)]
    return pruned


# ========= Timeout/Retry Utilities =========
def _with_timeout(fn, timeout: int):
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(fn)
        return fut.result(timeout=timeout)


def _invoke_model_safely(invoke_fn, timeout_s: int, max_retries: int):
    last_err = None
    for attempt in range(1, max_retries + 2):
        try:
            return _with_timeout(invoke_fn, timeout_s)
        except FuturesTimeout as e:
            last_err = e
            if logger.isEnabledFor(logging.WARNING):
                logger.warning("Model timeout (attempt %s/%s)", attempt, max_retries + 1)
        except Exception as e:
            last_err = e
            if logger.isEnabledFor(logging.WARNING):
                logger.warning("Model error (attempt %s/%s): %s", attempt, max_retries + 1, _preview.repr(e))
    raise last_err


def create_support_agent(agent_config: AgentConfig, config_manager: ConfigManager):
    """Create support agent using LDAI SDK pattern (tool-forward, LD-test-oriented)."""

    # ----- Knobs (allow LD to tune without code changes) -----
    knobs = getattr(agent_config, "knobs", {}) or {}

    FINAL_SENTINEL = knobs.get("final_sentinel", FINAL_SENTINEL_DEFAULT)
    MAX_TOOL_CALLS = int(knobs.get("max_tool_calls", MAX_TOOL_CALLS_DEFAULT))
    TARGET_MIN_TOOL_CALLS = int(knobs.get("target_min_tool_calls", TARGET_MIN_TOOL_CALLS_DEFAULT))
    MAX_ASSISTANT_TURNS = int(knobs.get("max_assistant_turns", MAX_ASSISTANT_TURNS_DEFAULT))
    SYNTHESIS_PATIENCE = int(knobs.get("synthesis_patience", SYNTHESIS_PATIENCE_DEFAULT))

    MODEL_TIMEOUT_S = int(knobs.get("model_timeout_s", MODEL_TIMEOUT_S_DEFAULT))
    MODEL_MAX_RETRIES = int(knobs.get("model_max_retries", MODEL_MAX_RETRIES_DEFAULT))

    TOOL_TIMEOUT_S = int(knobs.get("tool_timeout_s", TOOL_TIMEOUT_S_DEFAULT))
    TOOL_MAX_RETRIES = int(knobs.get("tool_max_retries", TOOL_MAX_RETRIES_DEFAULT))
    PARALLEL_TOOLS = bool(knobs.get("parallel_tools", PARALLEL_TOOLS_DEFAULT))
    MAX_PARALLEL = int(knobs.get("max_parallel_tools", MAX_PARALLEL_DEFAULT))
    TRUNCATE_TOOL_RESULT = int(knobs.get("truncate_tool_result_chars", TRUNCATE_TOOL_RESULT_DEFAULT))
    MAX_TOOL_MESSAGES_KEPT = int(knobs.get("max_tool_messages_kept", MAX_TOOL_MESSAGES_KEPT_DEFAULT))

    run_id = _run_id()
    if logger.isEnabledFor(logging.INFO):
        logger.info("🏗️  Creating support agent (run_id=%s) | model=%s", run_id, agent_config.model_name)

    # ----- Model -----
    model = config_manager.create_langchain_model(agent_config)
    tracker = agent_config.tracker

    # ----- Tools container -----
    available_tools: List[BaseTool] = []

    # ----- MCP tools loading (singleton) -----
    if logger.isEnabledFor(logging.INFO):
        logger.info("🔄 Loading MCP tools... (run_id=%s)", run_id)
    
    from tools_impl.mcp_runtime import MCPRuntime

    mcp_tool_map: Dict[str, Any] = {}
    try:
        mcp_runtime = MCPRuntime.instance()
        mcp_tool_map = {getattr(t, "name"): t for t in mcp_runtime.tools.values() if hasattr(t, "name")}
        if logger.isEnabledFor(logging.INFO):
            logger.info("✅ MCP tools loaded (singleton): %s", list(mcp_tool_map.keys()))
    except Exception as e:
        if logger.isEnabledFor(logging.ERROR):
            logger.error("❌ MCP singleton init error: %s; using internal tools only.", _preview.repr(e))
        mcp_tool_map = {}

    # Map LaunchDarkly tool names to actual MCP tool names
    ld_to_mcp_mapping = {
        "arxiv_search": "search_papers",
        "semantic_scholar": "search_semantic_scholar",
    }

    # Tools from config or defaults
    if agent_config.tools:
        configured_tools = agent_config.tools
        if logger.isEnabledFor(logging.INFO):
            logger.info("🛠️  Using tools from config: %s", configured_tools)
    else:
        configured_tools = [
            "search_v1",
            "search_v2",
            "reranking",
            "arxiv_search",
            "semantic_scholar",
        ]
        if logger.isEnabledFor(logging.WARNING):
            logger.warning("⚠️  No tools in config; using defaults: %s", configured_tools)

    # Wrapper for MCP tools
    class MCPToolWrapper(BaseTool):
        name: str
        description: str
        wrapped_tool: Any
        loop_runner: Any
        timeout_s: int

        def _host_from_args(self, args: Dict[str, Any]) -> Optional[str]:
            """Best-effort: extract hostname from args for backoff tracking."""
            for v in args.values():
                if isinstance(v, str) and v.startswith("http"):
                    try:
                        return urlparse(v).hostname
                    except Exception:
                        pass
            return None

        def _run(self, **kwargs) -> str:
            tool_kwargs = kwargs.get("kwargs", kwargs) or {}
            host = self._host_from_args(tool_kwargs) or "api.semanticscholar.org"

            # Respect global backoff for this host
            with _host_lock:
                until = _host_backoff_until.get(host)
                if until and until > datetime.utcnow():
                    wait = (until - datetime.utcnow()).total_seconds()
                    if logger.isEnabledFor(logging.WARNING):
                        logger.warning("⏳ Backing off %s for %.1fs due to prior 429", host, wait)
                    time.sleep(min(wait, self.timeout_s))

            max_retries = 3
            base_delay = 1.0

            with _concurrency:  # Global concurrency gate
                for attempt in range(max_retries + 1):
                    try:
                        if logger.isEnabledFor(logging.INFO):
                            logger.info("🔧 MCP[%s] attempt %d/%d args: %s", self.name, attempt + 1, max_retries + 1, _preview.repr(tool_kwargs))

                        # Schedule on the persistent loop
                        async def _call():
                            if hasattr(self.wrapped_tool, "ainvoke"):
                                return await self.wrapped_tool.ainvoke(tool_kwargs)
                            if hasattr(self.wrapped_tool, "_arun"):
                                return await self.wrapped_tool._arun(**tool_kwargs)
                            if hasattr(self.wrapped_tool, "invoke"):
                                res = self.wrapped_tool.invoke(tool_kwargs)
                                return await res if asyncio.iscoroutine(res) else res
                            raise RuntimeError("Wrapped MCP tool has no async entrypoint")

                        result = self.loop_runner.call(_call(), timeout=self.timeout_s)

                        text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)[:2000]
                        
                        # Detect 429s and pull Retry-After if present
                        lower = text.lower()
                        if " 429" in text or "rate limit" in lower:
                            retry_after_s = None
                            # Naive parse for Retry-After header
                            for token in lower.splitlines():
                                if "retry-after" in token:
                                    try:
                                        retry_after_s = int("".join(ch for ch in token if ch.isdigit()))
                                    except Exception:
                                        pass
                            
                            delay = retry_after_s or min(base_delay * (2 ** attempt), 30)
                            jitter = random.uniform(0.2, 0.8)
                            backoff = delay + jitter
                            
                            with _host_lock:
                                _host_backoff_until[host] = datetime.utcnow() + timedelta(seconds=backoff)
                            
                            if attempt < max_retries:
                                if logger.isEnabledFor(logging.WARNING):
                                    logger.warning("🔁 %s rate limited, retrying in %.2fs (attempt %d/%d)",
                                                   host, backoff, attempt + 1, max_retries + 1)
                                time.sleep(backoff)
                                continue
                            
                            return f"MCP tool '{self.name}' hit rate limit; retried {max_retries}x. Respecting backoff ~{int(backoff)}s."
                        
                        # Success
                        return text
                        
                    except Exception as e:
                        if attempt < max_retries:
                            delay = min(base_delay * (2 ** attempt), 10)
                            time.sleep(delay + random.uniform(0.1, 0.5))
                            continue
                        return f"MCP tool '{self.name}' error after retries: {e}"

    # Build tool list
    for tool_name in configured_tools:
        if logger.isEnabledFor(logging.INFO):
            logger.info("⚙️  Processing tool: %s", tool_name)
        if tool_name == "search_v1":
            available_tools.append(SearchToolV1())
        elif tool_name == "search_v2":
            available_tools.append(SearchToolV2())
        elif tool_name == "reranking":
            available_tools.append(RerankingTool())
        elif tool_name in ("arxiv_search", "semantic_scholar"):
            mcp_tool_name = ld_to_mcp_mapping.get(tool_name)
            if mcp_tool_name and mcp_tool_name in mcp_tool_map:
                mcp_tool = mcp_tool_map[mcp_tool_name]
                from tools_impl.mcp_runtime import MCPRuntime
                wrapped = MCPToolWrapper(
                    name=tool_name,
                    description=getattr(mcp_tool, "description", f"MCP tool: {mcp_tool_name}"),
                    wrapped_tool=mcp_tool,
                    loop_runner=MCPRuntime.instance().loop_runner,
                    timeout_s=TOOL_TIMEOUT_S,
                )
                available_tools.append(wrapped)
            else:
                if logger.isEnabledFor(logging.WARNING):
                    logger.warning("❌ MCP tool unavailable: %s (map: %s)", tool_name, list(mcp_tool_map.keys()))

    if logger.isEnabledFor(logging.INFO):
        logger.info("🔧 Final tools: %s", [getattr(t, "name", str(t)) for t in available_tools])

    # Tool palette text (for the model + for error guidance)
    def _tool_palette_text(tools: List[BaseTool]) -> str:
        lines = []
        for t in tools:
            name = getattr(t, "name", "?")
            desc = (getattr(t, "description", "") or "").strip().replace("\n", " ")
            lines.append(f"- {name}: {desc[:180]}")
        return "\n".join(lines) or "(none)"

    # ----- Bind tools & Tool Node -----
    if available_tools:
        model = model.bind_tools(available_tools)

        def _call_tool_with_timeout(tool: BaseTool, args: dict):
            def _invoke():
                try:
                    try:
                        return tool.invoke(args)
                    except TypeError:
                        return tool._run(**args)
                except Exception as e:
                    return f"Error: {e}"
            return _with_timeout(_invoke, TOOL_TIMEOUT_S)

        def _execute_one(tool: BaseTool, args: dict):
            # Check TTL cache for duplicate queries
            sig = (getattr(tool, "name", "?"), _norm_args(args))
            if sig in _tool_result_cache:
                if logger.isEnabledFor(logging.INFO):
                    logger.info("🔄 Cache hit for %s with args %s", sig[0], _preview.repr(sig[1]))
                return _tool_result_cache[sig]
            
            last_err = None
            for attempt in range(1, TOOL_MAX_RETRIES + 2):
                try:
                    result = _call_tool_with_timeout(tool, args)
                    # Cache successful result
                    _tool_result_cache[sig] = result
                    return result
                except FuturesTimeout as e:
                    last_err = e
                    if logger.isEnabledFor(logging.WARNING):
                        logger.warning(
                            "Tool timeout (attempt %s/%s) for %s",
                            attempt, TOOL_MAX_RETRIES + 1, getattr(tool, "name", "?")
                        )
                except Exception as e:
                    last_err = e
                    if logger.isEnabledFor(logging.WARNING):
                        logger.warning(
                            "Tool error (attempt %s/%s) for %s: %s",
                            attempt, TOOL_MAX_RETRIES + 1, getattr(tool, "name", "?"), _preview.repr(e)
                        )
            result = f"Tool failed after retries: {last_err}"
            # Don't cache failures
            return result

        def custom_tool_node(state: AgentState):
            messages = state["messages"]
            last_message = messages[-1]
            if not (hasattr(last_message, "tool_calls") and last_message.tool_calls):
                return {"messages": []}

            # Build call batch
            calls = []
            for idx, tc in enumerate(last_message.tool_calls):
                name = tc["name"]
                args = tc.get("args", {}) or {}
                tid = tc.get("id", f"{name}_{idx}")
                tool = next((t for t in available_tools if getattr(t, "name", None) == name), None)
                calls.append((idx, name, args, tid, tool))

            results = [None] * len(calls)
            tool_msgs: List[ToolMessage] = []
            last_query = None

            # Execute (parallel or serial)
            if PARALLEL_TOOLS:
                with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL, len(calls))) as ex:
                    futures = {}
                    for idx, name, args, tid, tool in calls:
                        if tool is None:
                            results[idx] = (tid, f"Error: Tool '{name}' not found")
                            continue
                        futures[ex.submit(_execute_one, tool, args)] = (idx, tid, name)
                    for fut in futures:
                        idx, tid, name = futures[fut]
                        try:
                            res = fut.result()
                        except Exception as e:
                            res = f"Unhandled tool execution error: {e}"
                        results[idx] = (tid, res)
            else:
                for idx, name, args, tid, tool in calls:
                    if tool is None:
                        results[idx] = (tid, f"Error: Tool '{name}' not found")
                        continue
                    res = _execute_one(tool, args)
                    results[idx] = (tid, res)

            # Build ToolMessages in original order
            for (idx, name, args, tid, tool), (_, res) in zip(calls, results):
                last_query = last_query or (args.get("query") or args.get("search_query") or args.get("q") or args.get("text"))
                if tool is None:
                    palette = _tool_palette_text(available_tools)
                    res = f"Error: Tool '{name}' not found. Available tools:\n{palette}"
                content = _truncate_text(res, TRUNCATE_TOOL_RESULT)
                tool_msgs.append(ToolMessage(content=str(content), tool_call_id=tid))

            return {
                "messages": tool_msgs,
                "most_recent_query": last_query or state.get("most_recent_query"),
                "most_recent_search_results": tool_msgs[-1].content if tool_msgs else state.get("most_recent_search_results"),
            }

        tool_node = custom_tool_node
    else:
        if logger.isEnabledFor(logging.WARNING):
            logger.warning("⚠️  No tools available; agent will operate model-only.")
        def noop_tool_node(state: AgentState):
            return {"messages": []}
        tool_node = noop_tool_node

    # ----- Router -----
    def should_continue(state: AgentState):
        msgs = state["messages"]
        last = msgs[-1]

        total_tool_calls = sum(len(getattr(m, "tool_calls", []) or []) for m in msgs)
        consecutive_no_tools = _consecutive_ai_without_tools(msgs)
        total_ai_msgs = sum(1 for m in msgs if isinstance(m, AIMessage))

        if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
            return "tools"

        if isinstance(last, ToolMessage):
            return "continue"

        if isinstance(last, AIMessage):
            content = (last.content or "")
            if (
                FINAL_SENTINEL in content
                or total_tool_calls >= MAX_TOOL_CALLS
                or consecutive_no_tools >= SYNTHESIS_PATIENCE
                or total_ai_msgs >= MAX_ASSISTANT_TURNS
            ):
                return "end"
            return "continue"

        return "continue"

    # ----- Model Invocation Node -----
    def call_model(state: AgentState):
        try:
            messages = _prune_messages(state["messages"], MAX_TOOL_MESSAGES_KEPT)

            total_tool_calls = sum(len(getattr(m, "tool_calls", []) or []) for m in messages)
            remaining = max(0, MAX_TOOL_CALLS - total_tool_calls)
            history = _collect_tool_history(messages, limit=12)

            # For extra nudge against repeats
            previous_queries: List[str] = []
            for m in messages:
                for tc in getattr(m, "tool_calls", []) or []:
                    args = tc.get("args", {}) or {}
                    q = args.get("query") or args.get("search_query") or args.get("q") or args.get("text")
                    if isinstance(q, str) and q.strip():
                        previous_queries.append(f"- {tc.get('name','?')}: '{q.strip()}'")

            is_synthesis_call = any(isinstance(m, ToolMessage) for m in messages[-3:]) if len(messages) > 1 else False

            # Inject SystemMessage with budgets, history, tool palette, finish rule
            if len(messages) == 1 or is_synthesis_call:
                previous_queries_text = ""
                if previous_queries:
                    previous_queries_text = (
                        "⚠️ PREVIOUS QUERIES ALREADY USED - DO NOT REPEAT EXACTLY:\n"
                        + "\n".join(previous_queries)
                    )

                base_instructions = agent_config.instructions
                system_prompt = base_instructions
                system_prompt = system_prompt.replace("{previous_queries}", previous_queries_text)
                system_prompt = system_prompt.replace("{max_tool_calls}", str(MAX_TOOL_CALLS))
                system_prompt = system_prompt.replace("{synthesis_mode}", "true" if is_synthesis_call else "false")
                if is_synthesis_call and "{{#if synthesis_mode" in system_prompt:
                    system_prompt = system_prompt.replace('{{#if synthesis_mode == "true"}}', "")
                    system_prompt = system_prompt.replace("{{/if}}", "")

                used_lines = "\n".join(f"- {name} :: {sig}" for (name, sig) in history) or "(none)"
                palette = _tool_palette_text(available_tools)

                system_prompt += f"""

# Tool-Use Mode (LaunchDarkly Testing)
- You can use up to **{MAX_TOOL_CALLS}** tool calls; remaining: **{remaining}**.
- Aim to reach at least **{TARGET_MIN_TOOL_CALLS}** tool calls if it improves quality.
- Prefer **unused tools** or **new arguments** when relevant.
- **Avoid exact duplicates**: do not call the same tool with identical normalized arguments (lowercased, trimmed, stable keys).
- If you must repeat a tool, **change the arguments** (broaden/narrow/synonymize) or briefly justify the repeat.

## CRITICAL: Reranking Tool Usage
**When calling `reranking`, you MUST pass `results` as the JSON `items` array from search_v2, NOT the human summary text.**
Example: If search_v2 returns ```json{{"items": [{{"text": "...", "score": 0.8}}]}}``` then pass `results=[{{"text": "...", "score": 0.8}}]`

## Tool history (unique by tool+normalized-args)
{used_lines}

## Tool palette
{palette}

## Finishing
When your answer is complete and you do not need further tools, end your message with:
{FINAL_SENTINEL}
"""

                messages = [SystemMessage(content=system_prompt)] + messages

            response = config_manager.track_metrics(
                tracker,
                lambda: _invoke_model_safely(lambda: model.invoke(messages), MODEL_TIMEOUT_S, MODEL_MAX_RETRIES)
            )

            if logger.isEnabledFor(logging.INFO):
                logger.info("Model responded (run_id=%s) | tool_calls=%s", state.get("run_id") or run_id, bool(getattr(response, "tool_calls", None)))
            return {"messages": [response], "run_id": state.get("run_id") or run_id}

        except Exception as e:
            if logger.isEnabledFor(logging.ERROR):
                logger.error("ERROR in call_model: %s", _preview.repr(e))
            try:
                config_manager.track_metrics(tracker, lambda: (_ for _ in ()).throw(e))
            except Exception:
                pass
            error_response = AIMessage(
                content="I encountered an error processing your request. Please try again."
            )
            return {"messages": [error_response], "run_id": state.get("run_id") or run_id}

    # ----- Final Formatting Node -----
    def format_final_response(state: AgentState):
        messages = state["messages"]
        tool_calls: List[str] = []
        tool_details: List[dict] = []

        mcp_to_ld_mapping = {
            "search_papers": "arxiv_search",
            "search_semantic_scholar": "semantic_scholar",
        }

        for message in messages:
            if hasattr(message, "tool_calls") and message.tool_calls:
                for call in message.tool_calls:
                    actual_tool_name = call["name"]
                    tool_args = call.get("args", {}) or {}
                    search_query = (
                        tool_args.get("query", "")
                        or tool_args.get("search_query", "")
                        or tool_args.get("q", "")
                        or tool_args.get("results", "")
                        or tool_args.get("text", "")
                        or (tool_args.get("kwargs", {}).get("query", "") if isinstance(tool_args.get("kwargs"), dict) else "")
                    )

                    display_tool_name = mcp_to_ld_mapping.get(actual_tool_name, actual_tool_name)
                    tool_calls.append(display_tool_name)
                    tool_details.append(
                        {"name": display_tool_name, "search_query": search_query or None, "args": tool_args}
                    )

        final_message = next(
            (m for m in reversed(messages) if isinstance(m, AIMessage) and getattr(m, "content", None)),
            None,
        )

        if final_message:
            final_response = final_message.content
            if isinstance(final_response, list):
                text_parts: List[str] = []
                for block in final_response:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif isinstance(block, str):
                        text_parts.append(block)
                final_response = " ".join(text_parts).strip()
            if isinstance(final_response, str):
                final_response = final_response.replace(FINAL_SENTINEL, "").strip()
            if not final_response:
                final_response = "I apologize, but I couldn't generate a proper response."
        else:
            final_response = "I apologize, but I couldn't generate a proper response."

        if logger.isEnabledFor(logging.INFO):
            logger.info("🔧 Returning final (run_id=%s) | tools=%s", state.get("run_id") or run_id, tool_calls)

        return {
            "user_input": state.get("user_input", ""),
            "response": final_response,
            "tool_calls": tool_calls,
            "tool_details": tool_details,
            "messages": messages,
            "run_id": state.get("run_id") or run_id,
        }

    # ----- Build the workflow -----
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", tool_node)
    workflow.add_node("format", format_final_response)

    workflow.set_entry_point("agent")

    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", "continue": "agent", "end": "format"},
    )

    workflow.add_edge("tools", "agent")
    workflow.set_finish_point("format")

    return workflow.compile()
