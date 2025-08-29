#!/usr/bin/env python3
"""
Direct test of tool_details data flow without web server overhead
"""

import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
from langchain_core.messages import HumanMessage
from agents.supervisor_agent import create_supervisor_agent
from agents.support_agent import create_support_agent
from policy.config_manager import ConfigManager
from ai_metrics import AIMetricsTracker

async def test_tool_details_flow():
    print("🧪 TESTING TOOL_DETAILS DATA FLOW")
    print("=" * 50)
    
    config_manager = ConfigManager()
    user_id = "debug_user"
    message = "Find information about machine learning"
    
    # Get configurations
    supervisor_config = await config_manager.get_config(user_id, "supervisor-agent")
    support_config = await config_manager.get_config(user_id, "support-agent")  
    security_config = await config_manager.get_config(user_id, "security-agent")
    
    print(f"📋 Support Agent Config:")
    print(f"   Model: {support_config.model}")
    print(f"   Variation: {support_config.variation_key}")
    print(f"   Allowed Tools: {getattr(support_config, 'allowed_tools', 'No tools attribute')}")
    print(f"   Config Keys: {list(vars(support_config).keys())}")
    
    # Create metrics tracker
    metrics_tracker = AIMetricsTracker(support_config.tracker)
    metrics_tracker.start_workflow(user_id, message)
    
    # Create supervisor agent
    supervisor_agent = create_supervisor_agent(
        supervisor_config, support_config, security_config, 
        metrics_tracker=metrics_tracker
    )
    
    # Test the support agent directly first
    print(f"🧪 TESTING SUPPORT AGENT DIRECTLY")
    print("=" * 30)
    
    support_agent = create_support_agent(support_config)
    support_input = {
        "user_input": message,
        "response": "",
        "tool_calls": [],
        "tool_details": [],
        "messages": [HumanMessage(content=message)]
    }
    
    direct_result = support_agent.invoke(support_input)
    print(f"🔧 DIRECT SUPPORT AGENT RESULT:")
    print(f"   📊 Type: {type(direct_result)}")
    print(f"   📊 Keys: {list(direct_result.keys()) if isinstance(direct_result, dict) else 'Not a dict'}")
    print(f"   📊 tool_calls: {direct_result.get('tool_calls', 'NO KEY')}")
    print(f"   📊 tool_details: {direct_result.get('tool_details', 'NO KEY')}")
    print(f"   📊 tool_details length: {len(direct_result.get('tool_details', []))}")
    
    print("\n🚀 Now testing full supervisor workflow:")
    print("=" * 50)
    
    # Test the workflow
    initial_state = {
        "user_input": message,
        "current_agent": "",
        "security_cleared": False,
        "support_response": "",
        "final_response": "",
        "workflow_stage": "initial_security",
        "messages": [HumanMessage(content=message)]
    }
    
    try:
        result = await supervisor_agent.ainvoke(initial_state)
        
        print(f"✅ WORKFLOW COMPLETED")
        print("=" * 50)
        print(f"📝 Final Response: {result.get('final_response', 'No response')}")
        print(f"🔧 Actual Tool Calls: {result.get('actual_tool_calls', [])}")
        print(f"📊 Support Tool Details: {result.get('support_tool_details', [])}")
        
        # Finalize metrics
        metrics_tracker.finalize_workflow(result["final_response"])
        
        return result
        
    except Exception as e:
        print(f"❌ WORKFLOW ERROR: {e}")
        import traceback
        traceback.print_exc()
        metrics_tracker.finalize_workflow(f"Error: {e}")
        return None

if __name__ == "__main__":
    asyncio.run(test_tool_details_flow())