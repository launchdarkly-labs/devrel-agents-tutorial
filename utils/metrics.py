"""Metrics tracking utilities for supervisor agent orchestration"""

import functools
from typing import Callable, Any, Optional
from utils.logger import log_debug


def track_supervisor_metrics(metric_name: str, config_manager: Any, supervisor_config: Any):
    """Decorator to track supervisor metrics with error handling"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                # Track operation start
                config_manager.track_metrics(
                    supervisor_config.tracker,
                    lambda: f"{metric_name}_start"
                )
                
                # Execute function
                result = func(*args, **kwargs)
                
                # Track successful completion
                config_manager.track_metrics(
                    supervisor_config.tracker,
                    lambda: f"{metric_name}_success"
                )
                
                return result
                
            except Exception as e:
                log_debug(f"❌ SUPERVISOR ERROR in {metric_name}: {e}")
                
                # Track error with LDAI metrics
                config_manager.track_metrics(
                    supervisor_config.tracker,
                    lambda: (_ for _ in ()).throw(e)  # Trigger error tracking
                )
                raise
        return wrapper
    return decorator


def track_supervisor_decision(config_manager: Any, supervisor_config: Any, next_agent: str):
    """Helper to track supervisor routing decisions"""
    config_manager.track_metrics(
        supervisor_config.tracker,
        lambda: f"supervisor_decision_success_{next_agent}"
    )


def track_workflow_completion(config_manager: Any, supervisor_config: Any, tool_calls: list):
    """Helper to track supervisor workflow completion"""
    config_manager.track_metrics(
        supervisor_config.tracker,
        lambda: f"supervisor_workflow_complete_tools_{len(tool_calls)}"
    )


def track_agent_orchestration(config_manager: Any, supervisor_config: Any, agent_name: str):
    """Helper to track agent orchestration start"""
    # Track orchestration start
    config_manager.track_metrics(
        supervisor_config.tracker,
        lambda: f"supervisor_orchestrating_{agent_name}_start"
    )


def track_agent_success(config_manager: Any, supervisor_config: Any, agent_name: str, tool_calls: Optional[list] = None):
    """Helper to track agent orchestration success"""
    if tool_calls is not None:
        config_manager.track_metrics(
            supervisor_config.tracker,
            lambda: f"supervisor_orchestrating_{agent_name}_success_tools_{len(tool_calls)}"
        )
    else:
        config_manager.track_metrics(
            supervisor_config.tracker,
            lambda: f"supervisor_orchestrating_{agent_name}_success"
        )