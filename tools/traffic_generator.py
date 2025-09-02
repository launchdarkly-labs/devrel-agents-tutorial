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
from pathlib import Path

# Dead simple configuration - edit these if you want!
API_BASE_URL = "http://localhost:8000"
USERS_FILE = "data/fake_users.json"
QUERIES_FILE = "data/sample_queries.json"

def load_json_file(filename):
    """Load a JSON file - helper function to keep things simple"""
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ ERROR: Couldn't load {filename}: {e}")
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
            print(f"✅ SUCCESS: Got {len(result['response'])} chars, used {len(result['tool_calls'])} tools")
            return result
        else:
            print(f"❌ ERROR: Status {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ REQUEST FAILED: {e}")
        return None

def simulate_feedback(response_data, query_data):
    """Simulate user feedback - this is where we fake thumbs up/down"""
    
    # Simple rules that anyone can understand and modify:
    thumbs_up_score = 0
    reasons = []
    
    response_text = response_data["response"].lower()
    response_length = len(response_data["response"])
    tools_used = response_data["tool_calls"]
    
    # Rule 1: Length matters
    if response_length > 200:
        thumbs_up_score += 30
        reasons.append("good length")
    elif response_length < 100:
        thumbs_up_score -= 20
        reasons.append("too short")
    
    # Rule 2: Check for good keywords
    good_keywords = query_data.get("good_response_keywords", [])
    keyword_matches = sum(1 for keyword in good_keywords if keyword.lower() in response_text)
    if keyword_matches > 0:
        thumbs_up_score += 25 * keyword_matches
        reasons.append(f"found {keyword_matches} keywords")
    
    # Rule 3: Research queries should mention papers
    if query_data.get("type") == "research":
        if any(word in response_text for word in ["paper", "research", "arxiv", "study"]):
            thumbs_up_score += 20
            reasons.append("mentions research")
        else:
            thumbs_up_score -= 30
            reasons.append("missing research content")
    
    # Rule 4: Tools used appropriately  
    if len(tools_used) > 0:
        thumbs_up_score += 15
        reasons.append("used tools")
    
    # Rule 5: Negative signals
    if any(phrase in response_text for phrase in ["i don't know", "i can't help", "i apologize"]):
        thumbs_up_score -= 25
        reasons.append("unhelpful response")
    
    # Convert score to thumbs up/down (add some randomness to make it realistic)
    random_factor = random.randint(-10, 10)
    final_score = thumbs_up_score + random_factor
    
    thumbs_up = final_score > 20  # If score is above 20, it's a thumbs up
    rating = max(1, min(5, round((final_score + 40) / 20)))  # Convert to 1-5 scale
    
    return {
        "thumbs_up": thumbs_up,
        "rating": rating,
        "score": final_score,
        "reasons": reasons
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
            print(f"❌ FEEDBACK FAILED: Status {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ FEEDBACK ERROR: {e}")
        return False

def flush_metrics():
    """Tell LaunchDarkly to send metrics immediately"""
    try:
        response = requests.post(f"{API_BASE_URL}/admin/flush", timeout=10)
        if response.status_code == 200:
            print("🚀 METRICS: Flushed to LaunchDarkly")
            return True
        else:
            print(f"❌ FLUSH FAILED: Status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ FLUSH ERROR: {e}")
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
    
    print(f"📊 LOADED: {len(users)} fake users, {len(queries)} sample queries")
    print(f"🎯 PLAN: Sending {args.queries} requests with {args.delay}s delays")
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
    print(f"\n🚀 FLUSHING: Sending metrics to LaunchDarkly...")
    flush_metrics()
    
    # Show final results
    print("\n" + "=" * 60)
    print("📊 FINAL RESULTS:")
    print(f"   Total requests: {total_requests}")
    print(f"   Successful requests: {successful_requests} ({successful_requests/total_requests*100:.1f}%)")
    print(f"   Successful feedback: {successful_feedback}")
    print(f"   Thumbs up: {thumbs_up_count}/{successful_feedback} ({thumbs_up_count/successful_feedback*100:.1f}%)" if successful_feedback > 0 else "   Thumbs up: 0%")
    print("\n✅ DONE! Check your LaunchDarkly dashboard for metrics.")
    print("🎉 TIP: It may take 1-2 minutes for metrics to appear in LaunchDarkly.")

if __name__ == "__main__":
    main()