#!/usr/bin/env python3
"""
Simple Traffic Generator with AI

1. Analyze knowledge base for topics
2. Generate queries using random topic/complexity
3. Send to API
4. Get AI feedback on response
5. Send feedback to API

Usage:
    python traffic_generator.py --queries 50 --delay 2
"""

import requests
import time
import argparse
import random
import os
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

class TrafficGenerator:
    def __init__(self):
        self.api_base_url = f"http://{os.getenv('API_HOST', 'localhost')}:{os.getenv('API_PORT', '8000')}"
        self.claude = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        
        # User context for API calls
        self.user_context = {
            "country": "US",
            "plan": "paid", 
            "region": "other"
        }
        
        # Unique user ID counter
        self.session_id = int(time.time())
        self.user_counter = 0

    def get_user_id(self):
        """Generate unique user ID"""
        self.user_counter += 1
        return f"user_{self.session_id}_{self.user_counter}"

    def analyze_knowledge_base(self):
        """Ask Claude to analyze KB and return topics"""
        print("Analyzing knowledge base...")
        
        try:
            response = self.claude.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=800,
                messages=[{
                    "role": "user",
                    "content": "List 15 technical topics that users would ask about regarding LaunchDarkly, feature flags, A/B testing, or deployment strategies. Just return a simple list of topics."
                }]
            )
            
            # Parse topics from response
            topics_text = response.content[0].text
            topics = [line.strip().strip('-•*123456789.') for line in topics_text.split('\n') if line.strip()]
            topics = [t for t in topics if len(t) > 3][:15]  # Clean and limit to 15
            
            if not topics:
                raise ValueError("No topics extracted")
                
            print(f"Found {len(topics)} topics")
            return topics
            
        except Exception as e:
            print(f"KB analysis failed, using defaults: {e}")
            return [
                "feature flags", "A/B testing", "user targeting",
                "rollout strategies", "SDK integration", "metrics",
                "deployment", "configuration", "debugging"
            ]

    def generate_query(self, topic, complexity):
        """Generate a query about the topic at given complexity"""
        prompt = f"""Generate a single question about "{topic}" at {complexity} level.
Just return the question, nothing else.

Complexity guide:
- basic: Simple what/how questions
- intermediate: Configuration or best practices
- advanced: Complex scenarios or architecture"""

        try:
            response = self.claude.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=150,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text.strip()
        except:
            # Fallback query
            templates = {
                "basic": f"What is {topic}?",
                "intermediate": f"How do I configure {topic}?",
                "advanced": f"What's the best architecture for {topic} at scale?"
            }
            return templates[complexity]

    def send_chat(self, query):
        """Send query to API and get response"""
        user_id = self.get_user_id()
        
        try:
            # Add user_id to context
            full_context = {**self.user_context, "user": user_id}

            response = requests.post(
                f"{self.api_base_url}/chat",
                json={
                    "message": query,
                    "user_id": user_id,
                    "user_context": full_context
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "user_id": user_id,
                    "conversation_id": data.get("id"),  # Use "id" field from response
                    "response": data.get("response", ""),
                    "variation_key": data.get("variation_key"),
                    "model": data.get("model"),
                    "tool_calls": data.get("tool_calls", [])  # Add tool_calls from response
                }
            else:
                return {"success": False}
                
        except Exception as e:
            print(f"  Chat error: {e}")
            return {"success": False}

    def evaluate_response(self, query, response):
        """Ask Claude to evaluate if user would give feedback"""
        prompt = f"""Based on this Q&A, would a user give feedback?

Question: {query[:200]}
Answer: {response[:500]}

Reply with ONLY one of these:
- positive (good answer, user would thumbs up)
- negative (poor answer, user would thumbs down)  
- none (okay answer, user wouldn't bother rating)

Most users don't give feedback unless the answer is notably good or bad."""

        try:
            response = self.claude.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=10,
                messages=[{"role": "user", "content": prompt}],
                timeout=2
            )
            
            feedback = response.content[0].text.strip().lower()
            if "positive" in feedback:
                return "positive"
            elif "negative" in feedback:
                return "negative"
            else:
                return "none"
                
        except:
            return "none"  # Default to no feedback on error

    def send_feedback(self, chat_data, query, feedback_type):
        """Send feedback to API"""
        if feedback_type == "none" or not chat_data["success"]:
            return
            
        try:
            requests.post(
                f"{self.api_base_url}/feedback",
                json={
                    "user_id": chat_data["user_id"],
                    "message_id": chat_data["conversation_id"],
                    "user_query": query,
                    "ai_response": chat_data["response"],
                    "feedback": feedback_type,
                    "variation_key": chat_data.get("variation_key", "unknown"),
                    "model": chat_data.get("model", "unknown"),
                    "tool_calls": chat_data.get("tool_calls", []),  # Add required tool_calls field
                    "source": "simulated"
                },
                timeout=10
            )
        except:
            pass  # Ignore feedback errors

    def run(self, num_queries, delay):
        """Main execution loop"""
        print(f"\n🚀 DEBUG: Starting {num_queries} queries with {delay}s delay\n")

        # Step 1: Get topics from knowledge base
        print("🔍 DEBUG: Step 1 - Analyzing knowledge base...")
        topics = self.analyze_knowledge_base()
        print(f"✅ DEBUG: Got {len(topics)} topics: {topics[:3]}...")
        complexities = ["basic", "intermediate", "advanced"]

        # Step 2: Generate and process queries
        print(f"🔍 DEBUG: Step 2 - Starting loop for {num_queries} queries...")
        for i in range(num_queries):
            print(f"\n🔍 DEBUG: Loop iteration {i+1}/{num_queries} starting...")

            # Random selection
            topic = random.choice(topics)
            complexity = random.choice(complexities)
            print(f"🔍 DEBUG: Selected topic='{topic}', complexity='{complexity}'")

            print(f"\n[{i+1}/{num_queries}] {topic} ({complexity})")

            # Generate query
            print("🔍 DEBUG: Calling generate_query...")
            query = self.generate_query(topic, complexity)
            print(f"✅ DEBUG: Generated query: {query[:50]}...")
            print(f"  Q: {query[:80]}...")

            # Add small delay to prevent Claude API rate limiting
            print("🔍 DEBUG: Adding 1s delay before API calls...")
            time.sleep(1)

            # Send to API
            print("🔍 DEBUG: Calling send_chat...")
            chat_data = self.send_chat(query)
            print(f"✅ DEBUG: send_chat returned: success={chat_data['success']}")

            if chat_data["success"]:
                print(f"  A: {chat_data['response'][:80]}...")

                # Add small delay before evaluation
                print("🔍 DEBUG: Adding 1s delay before evaluation...")
                time.sleep(1)

                # Evaluate response
                print("🔍 DEBUG: Calling evaluate_response...")
                feedback = self.evaluate_response(query, chat_data["response"])
                print(f"✅ DEBUG: evaluate_response returned: {feedback}")

                if feedback == "positive":
                    print("  👍 Positive feedback")
                elif feedback == "negative":
                    print("  👎 Negative feedback")
                else:
                    print("  😐 No feedback")

                # Send feedback to API
                print("🔍 DEBUG: Calling send_feedback...")
                self.send_feedback(chat_data, query, feedback)
                print("✅ DEBUG: send_feedback completed")
            else:
                print("  ❌ API call failed")

            print(f"🔍 DEBUG: Loop iteration {i+1}/{num_queries} completed")

            # Delay between requests
            if delay > 0 and i < num_queries - 1:
                print(f"🔍 DEBUG: Sleeping for {delay}s...")
                time.sleep(delay)

        print(f"\n🔍 DEBUG: Loop completed, reached end of run() method")
        print("\n✅ Complete\n")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--queries', type=int, default=50, help='Number of queries')
    parser.add_argument('--delay', type=float, default=2.0, help='Delay between queries')
    
    args = parser.parse_args()
    
    generator = TrafficGenerator()
    generator.run(args.queries, args.delay)

if __name__ == "__main__":
    main()