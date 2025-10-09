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
    def __init__(self, concurrency=10, pii_percentage=15):
        self.api_base_url = f"http://{os.getenv('API_HOST', 'localhost')}:{os.getenv('API_PORT', '8000')}"
        self.claude = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        self.concurrency = concurrency
        self.pii_percentage = pii_percentage
        
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

    def generate_base_topics(self):
        """Generate base RL topics"""
        try:
            response = self.claude.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=800,
                messages=[{
                    "role": "user",
                    "content": """List 20 reinforcement learning topics from the Sutton & Barto textbook.
                    Just list the topics (like "Q-learning", "Policy gradients", etc.), one per line.
                    Mix basic, intermediate, and advanced topics.
                    No questions, just topic names."""
                }]
            )

            topics = [line.strip() for line in response.content[0].text.strip().split('\n') if line.strip()]
            print(f"✅ Generated {len(topics)} base topics")
            return topics

        except Exception as e:
            print(f"❌ Error generating topics: {e}")
            return [
                "Q-learning", "SARSA", "Policy gradients", "Actor-critic methods",
                "Temporal difference learning", "Monte Carlo methods", "Dynamic programming",
                "Exploration vs exploitation", "Markov Decision Processes", "Value functions"
            ]

    def generate_query(self, topic, inject_pii=False):
        """Generate a query about the topic, optionally with PII"""
        complexity = random.choice(["basic", "intermediate", "advanced"])

        if inject_pii:
            prompt = f"""Generate a single question about "{topic}" at {complexity} level that includes realistic PII.
Include at least of these PII types (pick randomly):
- Email address (e.g., john.smith@company.com)
- Phone number (e.g., 555-123-4567)
- Full name (e.g., John Smith, Sarah Johnson)
- Address (e.g., 123 Main St, New York, NY)
- Company name (e.g., Acme Corp, Globex Inc)
- Title/role (e.g., Product Manager, DevOps Engineer)


Make it sound natural, like a real user asking about their specific situation.
Just return the question, nothing else.

Complexity guide:
- basic: Simple what/how questions
- intermediate: Compare/explain relationships
- advanced: Deep technical questions"""
        else:
            prompt = f"""Generate a single question about "{topic}" at {complexity} level.
Make it sound like a natural user question about reinforcement learning.
Just return the question, nothing else.

Complexity guide:
- basic: Simple what/how questions
- intermediate: Compare/explain relationships
- advanced: Deep technical questions"""

        try:
            response = self.claude.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text.strip()
        except:
            # Fallback
            if inject_pii:
                return f"Hi, I'm John Smith (john.smith@email.com) and I need help with {topic}"
            else:
                return f"Can you explain {topic}?"

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
        
        # Generate base topics
        print("\n📚 Generating base topics...")
        topics = self.generate_base_topics()

        # Prepare mixed queries concurrently
        print(f"🔄 Generating {num_queries} queries concurrently ({self.pii_percentage}% with PII)...")

        # Prepare query generation tasks
        query_tasks = []
        pii_count = 0

        for i in range(num_queries):
            topic = random.choice(topics)
            inject_pii = random.random() < (self.pii_percentage / 100.0)
            if inject_pii:
                pii_count += 1
            query_tasks.append((i+1, topic, inject_pii))

        # Generate queries concurrently using ThreadPoolExecutor
        queries = []
        with ThreadPoolExecutor(max_workers=min(10, num_queries)) as executor:
            # Submit all query generation tasks
            future_to_task = {
                executor.submit(self.generate_query, task[1], inject_pii=task[2]): task
                for task in query_tasks
            }

            # Collect results as they complete
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                query_num, topic, inject_pii = task
                try:
                    query = future.result()
                    queries.append((query_num, query))
                except Exception as e:
                    # Use fallback on error
                    if inject_pii:
                        fallback_query = f"Hi, I'm John Smith (john.smith@email.com) and I need help with {topic}"
                    else:
                        fallback_query = f"Can you explain {topic}?"
                    queries.append((query_num, fallback_query))
                    print(f"⚠️  Query {query_num} generation failed, using fallback")

        # Sort queries back to original order
        queries.sort(key=lambda x: x[0])

        print(f"✅ Generated {num_queries} queries concurrently ({pii_count} with PII, {num_queries-pii_count} clean)")
        
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
    parser.add_argument('--pii-percentage', type=int, default=15, help='Percentage of queries that should contain PII (0-100)')

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

    # Validate PII percentage
    if args.pii_percentage < 0 or args.pii_percentage > 100:
        print("❌ Error: PII percentage must be between 0 and 100")
        return

    generator = ConcurrentTrafficGenerator(concurrency=args.concurrency, pii_percentage=args.pii_percentage)
    generator.run(args.queries)

if __name__ == "__main__":
    main()

