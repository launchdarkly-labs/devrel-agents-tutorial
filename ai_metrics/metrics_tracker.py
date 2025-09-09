"""
AI Metrics Tracker for LaunchDarkly AI Configs

This module provides comprehensive AI metrics tracking integrated with multi-agent workflows.
Tracks duration, token usage, success/error rates, and agent-specific metrics.
"""

import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json
from ldai.tracker import TokenUsage, FeedbackKind

def track_langgraph_metrics(tracker, func):
    """
    Track LangGraph agent operations with LaunchDarkly metrics.
    
    This function follows the LaunchDarkly LDAI SDK pattern for tracking
    LangGraph agents, which store token usage in message.usage_metadata.
    
    :param tracker: The LaunchDarkly tracker instance.
    :param func: Function to track.
    :return: Result of the tracked function.
    """
    try:
        result = tracker.track_duration_of(func)
        tracker.track_success()
        
        # For LangGraph agents, usage_metadata is included on all messages that used AI
        total_input_tokens = 0
        total_output_tokens = 0
        total_tokens = 0

        if "messages" in result:
            for message in result['messages']:
                # Check for usage_metadata directly on the message
                if hasattr(message, "usage_metadata") and message.usage_metadata:
                    usage_data = message.usage_metadata
                    total_input_tokens += usage_data.get("input_tokens", 0)
                    total_output_tokens += usage_data.get("output_tokens", 0)
                    total_tokens += usage_data.get("total_tokens", 0)

        if total_tokens > 0:
            from ldai.tracker import TokenUsage
            token_usage = TokenUsage(
                input=total_input_tokens,
                output=total_output_tokens,
                total=total_tokens
            )
            tracker.track_tokens(token_usage)
    except Exception:
        tracker.track_error()
        raise
    return result


def track_langchain_metrics(tracker, func):
    """
    Track LangChain-specific operations using the official LaunchDarkly AI SDK pattern.

    This function will track the duration of the operation, the token
    usage, and the success or error status.

    If the provided function throws, then this method will also throw.

    In the case the provided function throws, this function will record the
    duration and an error.

    A failed operation will not have any token usage data.

    :param tracker: The LaunchDarkly tracker instance.
    :param func: Function to track.
    :return: Result of the tracked function.
    """
    
    try:
        # Use the tracker's built-in duration tracking which handles timing properly
        result = tracker.track_duration_of(func)
        
        # The tracker.track_duration_of already handles timing, so we don't need to calculate it again
        # Note: TTFT (Time To First Token) should only be tracked when actual streaming data is available
        
        tracker.track_success()
        print(f"✅ PROPER LAUNCHDARKLY TRACKING: Operation completed successfully")
        
        # Extract token usage from LangChain response - only track when data is available
        if hasattr(result, "usage_metadata") and result.usage_metadata:
            usage_data = result.usage_metadata
            # Only create TokenUsage if we have actual token data (not zeros)
            input_tokens = usage_data.get("input_tokens")
            output_tokens = usage_data.get("output_tokens") 
            total_tokens = usage_data.get("total_tokens")
            
            if any(tokens is not None and tokens > 0 for tokens in [input_tokens, output_tokens, total_tokens]):
                token_usage = TokenUsage(
                    input=input_tokens or 0,
                    output=output_tokens or 0,
                    total=total_tokens or (input_tokens or 0) + (output_tokens or 0)
                )
                tracker.track_tokens(token_usage)
                print(f"🎯 PROPER LD TOKEN TRACKING: {token_usage.total} tokens")
        elif hasattr(result, "response_metadata") and result.response_metadata:
            # Handle Anthropic Claude response format - only track when data is available
            metadata = result.response_metadata
            if isinstance(metadata, dict):
                usage = metadata.get('usage', {})
                if isinstance(usage, dict):
                    input_tokens = usage.get('input_tokens')
                    output_tokens = usage.get('output_tokens')
                    
                    # Only track if we have actual token data (not None or 0)
                    if input_tokens is not None and output_tokens is not None and (input_tokens > 0 or output_tokens > 0):
                        total_tokens = input_tokens + output_tokens
                        token_usage = TokenUsage(
                            input=input_tokens,
                            output=output_tokens,
                            total=total_tokens
                        )
                        tracker.track_tokens(token_usage)
                        print(f"🎯 PROPER LD TOKEN TRACKING: {total_tokens} tokens (Claude format)")
        
        print(f"✅ PROPER LAUNCHDARKLY TRACKING: Operation completed successfully")
        
    except Exception as e:
        tracker.track_error()
        print(f"❌ PROPER LAUNCHDARKLY TRACKING: Error occurred: {e}")
        raise

    return result

@dataclass
class AgentMetrics:
    """Metrics for individual agent in multi-agent workflow"""
    agent_name: str
    model: str
    variation_key: str
    duration_ms: float
    tool_calls: List[str]
    success: bool
    error_message: Optional[str] = None
    tokens_used: Optional[int] = None

@dataclass  
class MultiAgentMetrics:
    """Comprehensive metrics for multi-agent workflow"""
    total_duration_ms: float
    agent_metrics: List[AgentMetrics]
    overall_success: bool
    user_id: str
    query: str
    final_response_length: int
    total_tool_calls: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for logging"""
        return {
            "total_duration_ms": self.total_duration_ms,
            "overall_success": self.overall_success,
            "user_id": self.user_id,
            "query": self.query[:100] + "..." if len(self.query) > 100 else self.query,
            "final_response_length": self.final_response_length,
            "total_tool_calls": self.total_tool_calls,
            "agent_count": len(self.agent_metrics),
            "agents": [
                {
                    "name": agent.agent_name,
                    "model": agent.model,
                    "variation": agent.variation_key,
                    "duration_ms": agent.duration_ms,
                    "tools": agent.tool_calls,
                    "success": agent.success,
                    "tokens": agent.tokens_used
                } for agent in self.agent_metrics
            ]
        }

class AIMetricsTracker:
    """Wrapper for LaunchDarkly AI Config metrics tracking"""
    
    def __init__(self, tracker: Optional[object] = None):
        self.ld_tracker = tracker
        self.start_time = time.time()
        self.agent_metrics: List[AgentMetrics] = []
        self.overall_success = True
        self.user_id = ""
        self.query = ""
        
        # Debug: Check what methods are available on the tracker
        if tracker:
            pass  # Tracker exists - no debug needed
            # print(f"🔍 TRACKER DEBUG: Tracker type = {type(tracker)}")
            # print(f"🔍 TRACKER DEBUG: Available methods = {[method for method in dir(tracker) if not method.startswith('_')]}")
        else:
            pass  # No tracker provided
            # print(f"🔍 TRACKER DEBUG: No tracker provided (tracker is None)")
        
    def start_workflow(self, user_id: str, query: str):
        """Start tracking a multi-agent workflow"""
        self.start_time = time.time()
        self.user_id = user_id
        self.query = query
        self.agent_metrics = []
        self.overall_success = True
        print(f"🔍 AI METRICS: Starting workflow tracking for user {user_id}")
        
    def track_agent_start(self, agent_name: str, model: str, variation_key: str) -> float:
        """Track the start of an agent's execution"""
        start_time = time.time()
        print(f"🤖 AI METRICS: Agent {agent_name} started (model: {model}, variation: {variation_key})")
        return start_time
        
    def track_agent_completion(self, agent_name: str, model: str, variation_key: str, 
                              start_time: float, tool_calls: List[str], 
                              success: bool, error_message: Optional[str] = None,
                              tokens_used: Optional[int] = None):
        """Track the completion of an agent's execution"""
        duration_ms = (time.time() - start_time) * 1000
        
        agent_metric = AgentMetrics(
            agent_name=agent_name,
            model=model,
            variation_key=variation_key,
            duration_ms=duration_ms,
            tool_calls=tool_calls,
            success=success,
            error_message=error_message,
            tokens_used=tokens_used
        )
        
        self.agent_metrics.append(agent_metric)
        
        if not success:
            self.overall_success = False
            
        # Track metrics with LaunchDarkly AI SDK if available
        if self.ld_tracker:
            try:
                # Track duration
                self.ld_tracker.track_duration(int(duration_ms))
                
                # Track success/error
                if success:
                    self.ld_tracker.track_success()
                else:
                    self.ld_tracker.track_error()
                
                # Track token usage using proper TokenUsage object if available
                if tokens_used and tokens_used > 0 and hasattr(self.ld_tracker, 'track_tokens'):
                    try:
                        # Only track if we have actual token data, not estimates
                        # Note: This method should ideally receive input/output breakdown from the caller
                        token_usage = TokenUsage(
                            input=0,  # Unknown - would need actual data from model response
                            output=0,  # Unknown - would need actual data from model response  
                            total=tokens_used
                        )
                        self.ld_tracker.track_tokens(token_usage)
                        print(f"🎯 PROPER TOKEN TRACKING: {tokens_used} tokens (total only)")
                    except Exception as token_error:
                        print(f"⚠️  TOKEN TRACKING ERROR: {token_error}")
                    
                print(f"✅ AI METRICS: Tracked {agent_name} metrics to LaunchDarkly")
                
            except Exception as e:
                print(f"⚠️  AI METRICS WARNING: Failed to track to LaunchDarkly: {e}")
        
        print(f"📊 AI METRICS: Agent {agent_name} completed - Duration: {duration_ms:.2f}ms, Success: {success}, Tools: {len(tool_calls)}")
        
    def track_model_call(self, model_call_func, agent_name: str, *args, **kwargs):
        """Track a model call using the official LaunchDarkly AI SDK pattern"""
        if not self.ld_tracker:
            # No tracker available, just execute the call
            return model_call_func(*args, **kwargs)
            
        print(f"🚀 USING PROPER LAUNCHDARKLY AI SDK TRACKING for {agent_name}")
        
        # Use the official track_langchain_metrics pattern from LaunchDarkly
        result = track_langchain_metrics(self.ld_tracker, lambda: model_call_func(*args, **kwargs))
        
        print(f"✅ PROPER LD AI SDK TRACKING COMPLETED for {agent_name}")
        return result
    
    def _extract_token_usage(self, response) -> Optional[int]:
        """Extract token usage from model response"""
        try:
            # For Anthropic Claude responses
            if hasattr(response, 'response_metadata'):
                metadata = response.response_metadata
                if isinstance(metadata, dict):
                    # Check for usage info in various formats
                    usage = metadata.get('usage', {})
                    if isinstance(usage, dict):
                        input_tokens = usage.get('input_tokens', 0)
                        output_tokens = usage.get('output_tokens', 0)
                        return input_tokens + output_tokens
            
            # For OpenAI responses
            if hasattr(response, 'usage'):
                usage = response.usage
                if hasattr(usage, 'total_tokens'):
                    return usage.total_tokens
                elif hasattr(usage, 'prompt_tokens') and hasattr(usage, 'completion_tokens'):
                    return usage.prompt_tokens + usage.completion_tokens
            
            # Alternative check for usage in response dict
            if hasattr(response, '__dict__'):
                response_dict = response.__dict__
                if 'usage' in response_dict:
                    usage = response_dict['usage']
                    if isinstance(usage, dict):
                        return usage.get('total_tokens', 0)
            
            return None
            
        except Exception as e:
            print(f"⚠️  AI METRICS: Failed to extract token usage: {e}")
            return None
    
    def finalize_workflow(self, final_response: str) -> MultiAgentMetrics:
        """Finalize workflow tracking and return comprehensive metrics"""
        total_duration_ms = (time.time() - self.start_time) * 1000
        total_tool_calls = sum(len(agent.tool_calls) for agent in self.agent_metrics)
        
        metrics = MultiAgentMetrics(
            total_duration_ms=total_duration_ms,
            agent_metrics=self.agent_metrics,
            overall_success=self.overall_success,
            user_id=self.user_id,
            query=self.query,
            final_response_length=len(final_response),
            total_tool_calls=total_tool_calls
        )
        
        # Log comprehensive metrics
        metrics_dict = metrics.to_dict()
        print(f"📈 AI METRICS SUMMARY: {json.dumps(metrics_dict, indent=2)}")
        
        # Track final metrics to LaunchDarkly if available
        if self.ld_tracker:
            try:
                # Use feedback tracking for overall workflow satisfaction if available
                if hasattr(self.ld_tracker, 'track_feedback'):
                    try:
                        # Track success as positive feedback, failure as negative using SDK format
                        feedback_dict = {
                            "workflow_success": FeedbackKind.Positive if self.overall_success else FeedbackKind.Negative
                        }
                        self.ld_tracker.track_feedback(feedback_dict)
                    except Exception as feedback_error:
                        print(f"⚠️  FEEDBACK TRACKING ERROR: {feedback_error}")
                    
                # Get summary to show metrics were tracked
                try:
                    summary = self.ld_tracker.get_summary()
                    print(f"🚀 AI METRICS: Flushed metrics to LaunchDarkly - Duration: {summary.duration}ms")
                except Exception as summary_error:
                    print(f"🚀 AI METRICS: Metrics tracked to LaunchDarkly (no summary available: {summary_error})")
                
            except Exception as e:
                print(f"⚠️  AI METRICS WARNING: Failed to finalize LaunchDarkly metrics: {e}")
        
        return metrics
    
    async def submit_feedback_async(self, user_id: str, request_id: str, user_query: str, 
                                   ai_response: str, variation_key: str, model: str,
                                   tool_calls: List[str], thumbs_up: bool, source: str = "real_user"):
        """Submit user feedback to LaunchDarkly AI metrics"""
        try:
            if not self.ld_tracker:
                print(f"⚠️  AI METRICS: No LaunchDarkly tracker available for feedback submission")
                return False
            
            # Track satisfaction based on thumbs up/down using correct SDK method
            try:
                if hasattr(self.ld_tracker, 'track_feedback'):
                    # Use proper feedback format with FeedbackKind enum
                    from ldai.tracker import FeedbackKind
                    feedback_dict = {
                        "kind": FeedbackKind.Positive if thumbs_up else FeedbackKind.Negative
                    }
                    self.ld_tracker.track_feedback(feedback_dict)
                    print(f"📊 FEEDBACK TRACKED: {'👍 Positive' if thumbs_up else '👎 Negative'}")
                else:
                    print(f"⚠️  No track_feedback method available")
            except Exception as feedback_error:
                print(f"⚠️  FEEDBACK TRACKING ERROR: {feedback_error}")
                # Try alternative - treat feedback as success/error
                try:
                    if thumbs_up:
                        self.ld_tracker.track_success()
                    else:
                        self.ld_tracker.track_error()
                    print(f"📊 FEEDBACK AS SUCCESS/ERROR: {'success' if thumbs_up else 'error'}")
                except Exception as alt_error:
                    print(f"⚠️  ALTERNATIVE FEEDBACK TRACKING ERROR: {alt_error}")
            
            # Track additional metrics
            response_length = len(ai_response)
            self.ld_tracker.track_duration(0)  # No duration for feedback-only tracking
            
            if thumbs_up:
                self.ld_tracker.track_success()
            else:
                # Don't track as error for negative feedback - it's just user preference
                pass
            
            # Log feedback details
            feedback_details = {
                "user_id": user_id,
                "request_id": request_id,
                "variation_key": variation_key,
                "model": model,
                "thumbs_up": thumbs_up,
                "source": source,
                "query_length": len(user_query),
                "response_length": response_length,
                "tool_calls": tool_calls,
                "tools_used": len(tool_calls)
            }
            
            print(f"👍👎 AI FEEDBACK: {source} - {'👍' if thumbs_up else '👎'} for {variation_key}")
            print(f"📊 FEEDBACK DETAILS: {json.dumps(feedback_details, indent=2)}")
            
            # Flush feedback to LaunchDarkly immediately
            try:
                summary = self.ld_tracker.get_summary()
                print(f"🚀 FEEDBACK FLUSHED: Sent {source} feedback to LaunchDarkly")
            except Exception as e:
                print(f"⚠️  FEEDBACK FLUSH ERROR: {e}")
            
            return True
            
        except Exception as e:
            print(f"❌ FEEDBACK SUBMISSION ERROR: {e}")
            return False