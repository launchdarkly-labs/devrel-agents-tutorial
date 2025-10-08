#!/usr/bin/env python3
"""
Concurrent Traffic Generator - sends multiple requests in parallel

Usage:
    python concurrent_traffic_generator.py --queries 200 --concurrency 10
    
This will send 200 requests with up to 10 running at the same time.
"""

import requests
import time
import argparse
import random
import os
from dotenv import load_dotenv
from anthropic import Anthropic
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

load_dotenv()

class ConcurrentTrafficGenerator:
    def __init__(self, concurrency=10):
        self.api_base_url = f"http://{os.getenv('API_HOST', 'localhost')}:{os.getenv('API_PORT', '8000')}"
        self.claude = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        self.concurrency = concurrency
        
        # Thread-safe counters
        self.lock = Lock()
        self.completed = 0
        self.successful = 0
        self.failed = 0
        
        # User context for API calls (matches original traffic_generator.py)
        # Using ONLY other_paid to match experiment targeting
        self.user_context = {
            "country": "US",
            "region": "other",
            "plan": "paid"
        }
        
        # Unique user ID counter
        self.session_id = int(time.time())
        self.user_counter = 0
        self.user_counter_lock = Lock()

    def get_user_id(self):
        """Generate unique user ID (thread-safe)"""
        with self.user_counter_lock:
            self.user_counter += 1
            return f"user_{self.session_id}_{self.user_counter}"

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
            ai_response = self.claude.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=10,
                messages=[{"role": "user", "content": prompt}]
            )

            feedback = ai_response.content[0].text.strip().lower()
            if "positive" in feedback:
                return "positive"
            elif "negative" in feedback:
                return "negative"
            else:
                return "none"

        except:
            return "none"  # Default to no feedback on error

    def analyze_knowledge_base(self):
        """Ask Claude to analyze KB and return topics"""
        print("Analyzing knowledge base...")
        
        try:
            response = self.claude.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=1000,
                messages=[{
                    "role": "user",
                    "content": """Based on the context that this is a knowledge base about reinforcement learning 
                    (Sutton & Barto textbook), list 20 diverse topics or questions that users might ask.
                    
                    Mix complexity levels:
                    - 8 basic questions (What is...?, How does...?)
                    - 8 intermediate questions (Compare..., Explain the relationship...)
                    - 4 advanced questions (Deep technical questions)
                    
                    Format: One question per line, no numbering."""
                }]
            )
            
            topics = [line.strip() for line in response.content[0].text.strip().split('\n') if line.strip()]
            print(f"✅ Generated {len(topics)} topics")
            return topics
            
        except Exception as e:
            print(f"❌ Error analyzing KB: {e}")
            # Fallback topics
            return [
                "What is reinforcement learning?",
                "How do Q-learning and SARSA differ?",
                "Explain the exploration-exploitation tradeoff",
                "What are Markov Decision Processes?",
                "How does temporal difference learning work?",
            ]

    def send_single_request(self, query_num, query):
        """Send a single request and process response"""
        try:
            # Generate unique user
            user_id = self.get_user_id()
            # Use consistent context (other_paid) to match experiment targeting
            full_context = {**self.user_context, "user": user_id}
            
            # Send request
            start_time = time.time()
            response = requests.post(
                f"{self.api_base_url}/chat",
                json={
                    "message": query,
                    "user_id": user_id,
                    "user_context": full_context
                },
                timeout=2000  # 33 minutes
            )
            
            duration = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()

                # Use AI to evaluate response quality
                feedback = self.evaluate_response(query, data.get("response", ""))

                # Only send feedback if it's positive or negative (not "none")
                if feedback in ["positive", "negative"]:
                    try:
                        requests.post(
                            f"{self.api_base_url}/feedback",
                            json={
                                "user_id": user_id,
                                "message_id": data["id"],
                                "user_query": query,
                                "ai_response": data.get("response", ""),
                                "feedback": feedback,
                                "variation_key": data.get("variation_key", "unknown"),
                                "model": data.get("model", "unknown"),
                                "tool_calls": data.get("tool_calls", []),
                                "source": "simulated",
                                "user_context": full_context  # Critical: includes country, region, plan
                            },
                            timeout=10
                        )
                    except:
                        pass  # Feedback is optional
                
                with self.lock:
                    self.successful += 1
                    self.completed += 1
                    print(f"✅ [{self.completed}/{query_num}] Success ({duration:.1f}s) - other_paid: {query[:60]}...")
                
                return {"success": True, "duration": duration}
            else:
                with self.lock:
                    self.failed += 1
                    self.completed += 1
                    print(f"❌ [{self.completed}/{query_num}] Failed - {response.status_code}")
                
                return {"success": False, "error": response.status_code}
                
        except requests.exceptions.Timeout:
            with self.lock:
                self.failed += 1
                self.completed += 1
                print(f"⏱️  [{self.completed}/{query_num}] Timeout (>2000s) - {query[:60]}...")
            return {"success": False, "error": "timeout"}
            
        except Exception as e:
            with self.lock:
                self.failed += 1
                self.completed += 1
                print(f"❌ [{self.completed}/{query_num}] Error: {e}")
            return {"success": False, "error": str(e)}

    def run(self, num_queries):
        """Run traffic generation with concurrent requests"""
        print(f"\n🚀 Concurrent Traffic Generator")
        print(f"=" * 70)
        print(f"Queries: {num_queries}")
        print(f"Concurrency: {self.concurrency} parallel requests")
        print(f"Timeout: 2000s (33 minutes) per request")
        print(f"Target: {self.api_base_url}")
        print(f"=" * 70)
        
        # Generate queries
        print("\n📚 Analyzing knowledge base...")
        topics = self.analyze_knowledge_base()
        
        # Prepare queries
        queries = []
        for i in range(num_queries):
            query = random.choice(topics)
            queries.append((i+1, query))
        
        print(f"\n⚡ Sending {num_queries} requests with {self.concurrency} concurrent workers...")
        print()
        
        start_time = time.time()
        
        # Execute concurrent requests
        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            futures = {
                executor.submit(self.send_single_request, num, query): (num, query)
                for num, query in queries
            }
            
            # Wait for all to complete
            for future in as_completed(futures):
                pass  # Results are logged in send_single_request
        
        total_duration = time.time() - start_time
        
        # Summary
        print()
        print(f"=" * 70)
        print(f"✅ COMPLETE")
        print(f"=" * 70)
        print(f"Total time: {total_duration/60:.1f} minutes ({total_duration:.0f}s)")
        print(f"Successful: {self.successful}/{num_queries} ({100*self.successful/num_queries:.1f}%)")
        print(f"Failed: {self.failed}/{num_queries} ({100*self.failed/num_queries:.1f}%)")
        print(f"Average: {total_duration/num_queries:.1f}s per query (with concurrency)")
        print(f"=" * 70)

def main():
    parser = argparse.ArgumentParser(description='Concurrent traffic generator for AI agent testing')
    parser.add_argument('--queries', type=int, default=50, help='Number of queries to send')
    parser.add_argument('--concurrency', type=int, default=10, help='Number of concurrent requests')
    
    args = parser.parse_args()
    
    # Validate concurrency
    if args.concurrency < 1:
        print("❌ Error: concurrency must be at least 1")
        return
    if args.concurrency > 50:
        print("⚠️  Warning: High concurrency (>50) may overload the server")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            return
    
    generator = ConcurrentTrafficGenerator(concurrency=args.concurrency)
    generator.run(args.queries)

if __name__ == "__main__":
    main()

