#!/usr/bin/env python3
"""
Traffic Generator

Usage:
    python tools/traffic_generator.py --queries 50 --delay 2
    python tools/traffic_generator.py --queries 100 --delay 1 --verbose
"""

import json
import requests
import time
import random
import argparse
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration from environment variables with defaults
API_HOST = os.getenv('API_HOST', 'localhost')
API_PORT = os.getenv('API_PORT', '8000')
API_BASE_URL = f"http://{API_HOST}:{API_PORT}"
USERS_FILE = "data/fake_users.json"
QUERIES_FILE = "data/sample_queries.json"

def load_json_file(filename):
    """Load a JSON file - helper function to keep things simple"""
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f" ERROR: Couldn't load {filename}: {e}")
        return None

def send_chat_request(user, query_data):
    """Send a single chat request - returns the response or None if failed"""
    try:
        # Build the request - this is what gets sent to our AI agent
        request_data = {
            "user_id": user["id"],
            "message": query_data["query"],
            "user_context": {
                "country": user["country"],
                "region": user["region"], 
                "plan": user["plan"]
            }
        }
        
        print(f"🤖 SENDING: {user['id']} from {user['country']} asks: '{query_data['query'][:50]}...'")
        
        # Make the API call
        response = requests.post(f"{API_BASE_URL}/chat", json=request_data, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            print(f" SUCCESS: Got {len(result['response'])} chars, used {len(result['tool_calls'])} tools")
            return result
        else:
            print(f" ERROR: Status {response.status_code}")
            return None
            
    except Exception as e:
        print(f" REQUEST FAILED: {e}")
        return None

def simulate_feedback(response_data, query_data):
    """Simulate only user thumbs up/down decision - based on realistic user behavior"""

    # Simple baseline satisfaction rate (mimics real user feedback patterns)
    base_satisfaction_rate = 0.75  # 75% baseline satisfaction

    # Adjust satisfaction based on actual metrics we track in the UI:

    # 1. Response quality indicators (what users actually see)
    response_text = response_data["response"].lower()
    response_length = len(response_data["response"])
    tools_used = response_data["tool_calls"]

    satisfaction_modifier = 0

    # Obvious quality issues that users notice
    if response_length < 50:
        satisfaction_modifier -= 0.3  # Very short responses are unsatisfying
    elif any(phrase in response_text for phrase in ["i don't know", "i can't help", "sorry, i cannot"]):
        satisfaction_modifier -= 0.4  # Users don't like "can't help" responses

    # Positive indicators users notice
    if len(tools_used) > 0 and query_data.get("type") == "research":
        satisfaction_modifier += 0.1  # Users like when research tools are used for research queries

    # Final satisfaction rate with randomness to simulate individual user preferences
    final_satisfaction_rate = base_satisfaction_rate + satisfaction_modifier + random.uniform(-0.1, 0.1)
    final_satisfaction_rate = max(0.1, min(0.9, final_satisfaction_rate))  # Keep between 10-90%

    thumbs_up = random.random() < final_satisfaction_rate

    return {
        "thumbs_up": thumbs_up,
        "satisfaction_rate": final_satisfaction_rate  # For debugging only
    }

def send_feedback(response_data, user_id, query_data, feedback_data):
    """Send feedback to the API using the new format"""
    try:
        # Convert thumbs up/down to positive/negative
        feedback_type = "positive" if feedback_data["thumbs_up"] else "negative"
        
        feedback_request = {
            "user_id": user_id,
            "message_id": f"sim_{response_data.get('id', 'unknown')}_{int(time.time())}",
            "user_query": query_data["query"],
            "ai_response": response_data["response"],
            "feedback": feedback_type,
            "variation_key": response_data.get("variation_key", "unknown"),
            "model": response_data.get("model", "unknown"),
            "tool_calls": response_data.get("tool_calls", []),
            "source": "simulated"
        }
        
        response = requests.post(f"{API_BASE_URL}/feedback", json=feedback_request, timeout=10)
        
        if response.status_code == 200:
            print(f"👍 FEEDBACK: {user_id} gave {'👍' if feedback_data['thumbs_up'] else '👎'} "
                  f"(rating: {feedback_data['rating']}/5) - {', '.join(feedback_data['reasons'])}")
            return True
        else:
            print(f" FEEDBACK FAILED: Status {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f" FEEDBACK ERROR: {e}")
        return False

def flush_metrics():
    """Tell LaunchDarkly to send metrics immediately"""
    try:
        response = requests.post(f"{API_BASE_URL}/admin/flush", timeout=10)
        if response.status_code == 200:
            print(" METRICS: Flushed to LaunchDarkly")
            return True
        else:
            print(f" FLUSH FAILED: Status {response.status_code}")
            return False
    except Exception as e:
        print(f" FLUSH ERROR: {e}")
        return False

def main():
    """Main function - this is where everything happens"""
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Generate traffic for LaunchDarkly AI Config demo")
    parser.add_argument("--queries", type=int, default=20, help="Number of queries to send")
    parser.add_argument("--delay", type=float, default=2.0, help="Seconds between requests")
    parser.add_argument("--verbose", action="store_true", help="Show more details")
    args = parser.parse_args()
    
    # Load our data files
    print("📁 LOADING: Reading fake users and sample queries...")
    users_data = load_json_file(USERS_FILE)
    queries_data = load_json_file(QUERIES_FILE)
    
    if not users_data or not queries_data:
        print("💥 FATAL: Couldn't load data files. Make sure they exist!")
        return
    
    users = users_data["users"]
    queries = queries_data["queries"]
    
    print(f" LOADED: {len(users)} fake users, {len(queries)} sample queries")
    print(f" PLAN: Sending {args.queries} requests with {args.delay}s delays")
    print("=" * 60)
    
    # Keep track of results
    total_requests = 0
    successful_requests = 0
    successful_feedback = 0
    thumbs_up_count = 0
    
    # Main loop - send requests one by one
    for i in range(args.queries):
        print(f"\n📈 REQUEST {i+1}/{args.queries}")
        
        # Pick a random user and query
        user = random.choice(users)
        query = random.choice(queries)
        
        # Send the chat request
        total_requests += 1
        response_data = send_chat_request(user, query)
        
        if response_data:
            successful_requests += 1
            
            # Simulate user feedback
            feedback = simulate_feedback(response_data, query)
            
            # Send the feedback
            if send_feedback(response_data, user["id"], query, feedback):
                successful_feedback += 1
                if feedback["thumbs_up"]:
                    thumbs_up_count += 1
        
        # Wait before next request (unless it's the last one)
        if i < args.queries - 1:
            time.sleep(args.delay)
    
    # Flush metrics to LaunchDarkly
    print(f"\n FLUSHING: Sending metrics to LaunchDarkly...")
    flush_metrics()
    
    # Show final results
    print("\n" + "=" * 60)
    print(" FINAL RESULTS:")
    print(f"   Total requests: {total_requests}")
    print(f"   Successful requests: {successful_requests} ({successful_requests/total_requests*100:.1f}%)")
    print(f"   Successful feedback: {successful_feedback}")
    print(f"   Thumbs up: {thumbs_up_count}/{successful_feedback} ({thumbs_up_count/successful_feedback*100:.1f}%)" if successful_feedback > 0 else "   Thumbs up: 0%")
    print("\n DONE! Check your LaunchDarkly dashboard for metrics.")
    print("🎉 TIP: It may take 1-2 minutes for metrics to appear in LaunchDarkly.")

if __name__ == "__main__":
    main()