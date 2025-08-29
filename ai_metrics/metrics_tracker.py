"""
AI Metrics Tracker for LaunchDarkly AI Configs

This module provides comprehensive AI metrics tracking integrated with multi-agent workflows.
Tracks duration, token usage, success/error rates, and agent-specific metrics.
"""

import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json
from ldai.tracker import LDAIConfigTracker

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
    
    def __init__(self, tracker: Optional[LDAIConfigTracker] = None):
        self.ld_tracker = tracker
        self.start_time = time.time()
        self.agent_metrics: List[AgentMetrics] = []
        self.overall_success = True
        self.user_id = ""
        self.query = ""
        
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
                
                # Track token usage if available
                if tokens_used:
                    # Estimate input and output tokens (simplified)
                    estimated_input = tokens_used // 2
                    estimated_output = tokens_used - estimated_input
                    self.ld_tracker.track_token_usage(estimated_input, estimated_output)
                    
                print(f"✅ AI METRICS: Tracked {agent_name} metrics to LaunchDarkly")
                
            except Exception as e:
                print(f"⚠️  AI METRICS WARNING: Failed to track to LaunchDarkly: {e}")
        
        print(f"📊 AI METRICS: Agent {agent_name} completed - Duration: {duration_ms:.2f}ms, Success: {success}, Tools: {len(tool_calls)}")
        
    def track_model_call(self, model_call_func, agent_name: str, *args, **kwargs):
        """Track a model call with automatic duration and error handling"""
        if not self.ld_tracker:
            # No tracker available, just execute the call
            return model_call_func(*args, **kwargs)
            
        try:
            # Use LaunchDarkly's track_anthropic_metrics or similar if available
            # For now, we'll track manually
            start_time = time.time()
            result = model_call_func(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000
            
            # Track duration and success
            self.ld_tracker.track_duration(int(duration_ms))
            self.ld_tracker.track_success()
            
            print(f"🔄 AI METRICS: Model call for {agent_name} tracked - {duration_ms:.2f}ms")
            return result
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.ld_tracker.track_duration(int(duration_ms))
            self.ld_tracker.track_error()
            
            print(f"❌ AI METRICS: Model call for {agent_name} failed - {duration_ms:.2f}ms, Error: {e}")
            raise
    
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
                # Track overall workflow satisfaction (simplified as success)
                if self.overall_success:
                    self.ld_tracker.track_output_satisfaction(1.0)  # 100% satisfaction for successful workflows
                else:
                    self.ld_tracker.track_output_satisfaction(0.0)  # 0% satisfaction for failed workflows
                    
                # Flush metrics to LaunchDarkly
                summary = self.ld_tracker.get_summary()
                print(f"🚀 AI METRICS: Flushed metrics to LaunchDarkly - Duration: {summary.duration}ms")
                
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
            
            # Track satisfaction based on thumbs up/down
            satisfaction_score = 1.0 if thumbs_up else 0.0
            self.ld_tracker.track_output_satisfaction(satisfaction_score)
            
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
                print(f"🚀 FEEDBACK FLUSHED: Sent {source} feedback to LaunchDarkly - Satisfaction: {satisfaction_score}")
            except Exception as e:
                print(f"⚠️  FEEDBACK FLUSH ERROR: {e}")
            
            return True
            
        except Exception as e:
            print(f"❌ FEEDBACK SUBMISSION ERROR: {e}")
            return False