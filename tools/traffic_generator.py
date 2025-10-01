#!/usr/bin/env python3
"""
Dynamic Traffic Generator

Generates realistic queries with 3-option feedback simulation (thumbs up, thumbs down, no feedback).
Uses random topic/complexity selection and tracks both engagement and satisfaction rates.

Usage:
    python tools/traffic_generator.py --queries 50 --delay 2
    python tools/traffic_generator.py --queries 100 --delay 1
"""

import requests
import time
import argparse
import random
import os
from dotenv import load_dotenv
from anthropic import Anthropic

# Load environment variables
load_dotenv()

class DynamicExperimentGenerator:
    # Constants for API configuration
    CLAUDE_MODEL = "claude-3-haiku-20240307"
    KB_ANALYSIS_TOKENS = 800
    QUERY_GENERATION_TOKENS = 200
    EVALUATION_TOKENS = 50
    CHAT_TIMEOUT = 30
    FEEDBACK_TIMEOUT = 10

    def __init__(self):
        self.api_host = os.getenv('API_HOST', 'localhost')
        self.api_port = os.getenv('API_PORT', '8000')
        self.api_base_url = f"http://{self.api_host}:{self.api_port}"
        # Initialize direct Claude API client for internal operations
        self.claude_client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

        # Static context for other-paid segment targeting
        self.user_context = {
            "country": "US",
            "plan": "paid",
            "region": "other"
        }

        print(f"Using static other-paid user context for experiments")
        print(f"Using direct Claude API for internal KB analysis and evaluation")


    def _generate_user_id(self, suffix=""):
        """Generate consistent user IDs"""
        timestamp = int(time.time())
        if suffix:
            return f"traffic_user_{timestamp}_{suffix[:10]}"
        return f"traffic_user_{timestamp}"

    def analyze_knowledge_base(self):
        """Use direct Claude API to analyze KB and extract structured data"""
        print("Analyzing knowledge base content via direct Claude API...")

        analysis_prompt = """Analyze the available knowledge base and provide at least 10 specific topics that users would ask questions about.

Example output structure:
{
    "topics": [
        "LaunchDarkly feature flags", "AI model configurations", "A/B testing experiments",
        "User segmentation rules", "Targeting conditions", "Variation management",
        "Metrics and analytics", "Rollout strategies", "Environment configuration",
        "SDK integration", "Troubleshooting issues", "Performance optimization",
        "Security best practices", "Team collaboration", "API endpoints"
    ]
}

Provide at least 10 topics for good randomization."""

        try:
            response = self.claude_client.messages.create(
                model=self.CLAUDE_MODEL,
                max_tokens=self.KB_ANALYSIS_TOKENS,
                tools=[{
                    "name": "analyze_knowledge_base",
                    "description": "Analyze knowledge base structure and content",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "topics": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "At least 10 specific topics users would ask about",
                                "minItems": 10
                            }
                        },
                        "required": ["topics"]
                    }
                }],
                tool_choice={"type": "tool", "name": "analyze_knowledge_base"},
                messages=[{
                    "role": "user",
                    "content": analysis_prompt
                }]
            )

            if response.content and response.content[0].type == "tool_use":
                kb_data = response.content[0].input
                topics = kb_data.get('topics', [])
                print(f"✅ KB analysis complete: {len(topics)} topics available for query generation")
                return topics
            else:
                print("❌ No tool call found in KB analysis")
                return None

        except Exception as e:
            print(f"❌ KB analysis error: {e}")
            return None

    def generate_single_query(self, topics):
        """Generate a single query using random topic and complexity selection"""
        try:
            # Randomly select topic and complexity
            selected_topic = random.choice(topics)
            complexity = random.choice(["basic", "intermediate", "advanced"])

            prompt = f"""Generate 1 realistic user query about "{selected_topic}" at {complexity} complexity level.

Requirements:
- Focus specifically on {selected_topic}
- Make it {complexity} level difficulty
- Use natural language that real users would ask
- Be specific and relevant to the topic"""

            response = self.claude_client.messages.create(
                model=self.CLAUDE_MODEL,
                max_tokens=self.QUERY_GENERATION_TOKENS,
                tools=[{
                    "name": "generate_query",
                    "description": "Generate a single user query",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "The user question"},
                            "complexity": {"type": "string", "enum": ["basic", "intermediate", "advanced"]}
                        },
                        "required": ["query", "complexity"]
                    }
                }],
                tool_choice={"type": "tool", "name": "generate_query"},
                messages=[{"role": "user", "content": prompt}]
            )

            if response.content and response.content[0].type == "tool_use":
                query_data = response.content[0].input
                query_data["topic"] = selected_topic
                query_data["complexity"] = complexity
                return query_data
            return None

        except Exception as e:
            print(f"  ❌ Query generation error: {e}")
            return None

    def execute_single_query(self, query_data, delay):
        """Execute a single query and send feedback - returns (success, feedback_data)"""
        try:
            user_id = self._generate_user_id(query_data['query'])

            chat_request = {
                "message": query_data["query"],
                "user_id": user_id,
                "context": self.user_context
            }

            response = requests.post(
                f"{self.api_base_url}/chat",
                json=chat_request,
                timeout=self.CHAT_TIMEOUT
            )

            if response.status_code == 200:
                response_data = response.json()
                print(f"    ✅ Response: {response_data.get('response', '')[:50]}...")

                # Evaluate and send feedback
                evaluation = self.evaluate_response_quality(
                    query_data["query"],
                    response_data.get('response', '')
                )

                if evaluation:
                    feedback_choice = evaluation.get("feedback_choice")
                    if feedback_choice == "no_feedback":
                        print(f"    😐 No feedback (user wouldn't bother rating)")
                    else:
                        conversation_id = response_data.get('conversation_id')
                        if conversation_id and self.send_feedback(conversation_id, user_id, evaluation):
                            emoji = "👍" if evaluation["thumbs_up"] else "👎"
                            print(f"    📝 Feedback: {emoji} sent to LaunchDarkly")

                    # Delay before next request
                    if delay > 0:
                        time.sleep(delay)

                    return True, evaluation
                else:
                    print(f"    ⚠️ Skipping feedback (evaluation failed)")
                    return True, None
            else:
                print(f"    ❌ API call failed: {response.status_code}")
                return False, None

        except Exception as e:
            print(f"    ❌ Execution error: {e}")
            return False, None

    def evaluate_response_quality(self, query, response_text):
        """Use Claude tool calling to evaluate response quality - minimal tokens"""
        evaluation_prompt = f"""Evaluate whether a real user would provide feedback on this AI response.

QUERY: {query}

RESPONSE: {response_text}

Choose ONE of these realistic user behaviors:
- thumbs_up: Response is clearly helpful and satisfactory - user would actively like it
- thumbs_down: Response is clearly unhelpful or unsatisfactory - user would actively dislike it
- no_feedback: Response is okay but not compelling enough for user to bother rating (most common)

Be realistic: Most users don't provide feedback unless the response is clearly excellent or clearly poor."""

        try:
            response = self.claude_client.messages.create(
                model=self.CLAUDE_MODEL,
                max_tokens=self.EVALUATION_TOKENS,
                tools=[{
                    "name": "rate_response",
                    "description": "Rate response with 3 explicit options",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "feedback_choice": {
                                "type": "string",
                                "enum": ["thumbs_up", "thumbs_down", "no_feedback"],
                                "description": "Explicit choice: thumbs_up (satisfactory), thumbs_down (unsatisfactory), or no_feedback (user wouldn't bother rating)"
                            }
                        },
                        "required": ["feedback_choice"]
                    }
                }],
                tool_choice={"type": "tool", "name": "rate_response"},
                messages=[{
                    "role": "user",
                    "content": evaluation_prompt
                }]
            )

            # Extract structured data from tool call
            if response.content and response.content[0].type == "tool_use":
                evaluation = response.content[0].input
                feedback_choice = evaluation.get("feedback_choice")

                # Add compatibility fields based on feedback choice
                if feedback_choice == "thumbs_up":
                    evaluation["thumbs_up"] = True
                elif feedback_choice == "thumbs_down":
                    evaluation["thumbs_up"] = False
                else:  # no_feedback
                    evaluation["thumbs_up"] = None

                evaluation["reasoning"] = f"LLM evaluation: {feedback_choice}"
                return evaluation
            else:
                print("❌ No tool call found in evaluation response")
                return None

        except Exception as e:
            print(f"⚠️ Evaluation error: {e}")
            return None

    def send_feedback(self, conversation_id, user_id, evaluation):
        """Send feedback to the API based on LLM evaluation"""
        try:
            # Skip if no feedback should be sent
            if evaluation.get("thumbs_up") is None:
                return False

            feedback_type = "positive" if evaluation["thumbs_up"] else "negative"

            feedback_request = {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "feedback": feedback_type,
                "metadata": {
                    "reasoning": evaluation.get("reasoning", ""),
                    "source": "llm_evaluation"
                }
            }

            response = requests.post(
                f"{self.api_base_url}/feedback",
                json=feedback_request,
                timeout=self.FEEDBACK_TIMEOUT
            )

            if response.status_code == 200:
                emoji = "👍" if evaluation["thumbs_up"] else "👎"
                print(f"  📝 {emoji} Feedback sent: {evaluation['reasoning'][:50]}...")
                return True
            else:
                print(f"  ❌ Feedback failed: {response.status_code}")
                return False

        except Exception as e:
            print(f"  ❌ Feedback error: {e}")
            return False

    def run_experiment_generation(self, num_queries, delay_seconds):
        """Execute traffic generation with real-time engagement and satisfaction tracking"""
        print(f"\n🚀 Starting traffic generation: {num_queries} queries, {delay_seconds}s delay")
        print(f"📊 Target: other-paid segment for Premium Model Value Analysis")
        print(f"🎯 Experiment: Claude Opus 4 vs GPT-4o satisfaction comparison")
        print("-" * 60)

        # Analyze knowledge base once to get topics
        print("📚 Analyzing knowledge base...")
        kb_analysis = self.analyze_knowledge_base()
        if not kb_analysis or not kb_analysis.get('topics'):
            print("❌ Failed to analyze knowledge base")
            return

        topics = kb_analysis['topics']
        print(f"🔍 Found {len(topics)} topics for query generation")

        # Track both engagement and satisfaction metrics
        metrics = {
            "total_queries": 0,
            "thumbs_up": 0,
            "thumbs_down": 0,
            "no_feedback": 0
        }

        for i in range(num_queries):
            try:
                # Randomly select topic and complexity
                selected_topic = random.choice(topics)
                complexity = random.choice(["basic", "intermediate", "advanced"])

                print(f"\n📝 Query {i+1}/{num_queries} | Topic: {selected_topic} ({complexity})")

                # Generate single query
                query_data = self.generate_single_query(topics)
                if not query_data:
                    print("❌ Failed to generate query")
                    continue

                query_text = query_data.get("query", "")
                print(f"❓ Query: {query_text[:100]}...")

                # Execute query
                success, feedback = self.execute_single_query(query_data, delay_seconds)
                if not success:
                    print("❌ Failed to execute query")
                    continue

                metrics["total_queries"] += 1

                # Track feedback metrics
                if feedback:
                    feedback_choice = feedback.get("feedback_choice", "no_feedback")
                    metrics[feedback_choice] += 1

                    if feedback_choice == "thumbs_up":
                        print(f"🎯 Feedback: 👍 thumbs_up")
                    elif feedback_choice == "thumbs_down":
                        print(f"🎯 Feedback: 👎 thumbs_down")
                    else:
                        print(f"🎯 Feedback: 😐 no_feedback")
                else:
                    # Evaluation failed - count as no_feedback
                    metrics["no_feedback"] += 1
                    print(f"🎯 Feedback: ⚠️ evaluation_failed (counted as no_feedback)")

                # Progress summary with both metrics
                engagement_count = metrics["thumbs_up"] + metrics["thumbs_down"]
                if metrics["total_queries"] > 0:
                    engagement_rate = engagement_count / metrics["total_queries"]
                    satisfaction_rate = metrics["thumbs_up"] / engagement_count if engagement_count > 0 else 0
                    print(f"📈 Engagement: {engagement_rate:.1%} ({engagement_count}/{metrics['total_queries']}) | Satisfaction: {satisfaction_rate:.1%} ({metrics['thumbs_up']}/{engagement_count})")

                # Delay between queries
                if delay_seconds > 0 and i < num_queries - 1:
                    time.sleep(delay_seconds)

            except Exception as e:
                print(f"❌ Error on query {i+1}: {e}")
                continue

        # Final summary with both metrics
        print("\n" + "=" * 60)
        print("🏁 EXPERIMENT COMPLETE")
        print(f"📊 Total queries: {metrics['total_queries']}")

        engagement_count = metrics["thumbs_up"] + metrics["thumbs_down"]
        if metrics["total_queries"] > 0:
            engagement_rate = engagement_count / metrics["total_queries"]
            satisfaction_rate = metrics["thumbs_up"] / engagement_count if engagement_count > 0 else 0

            print(f"👍 Thumbs up: {metrics['thumbs_up']}")
            print(f"👎 Thumbs down: {metrics['thumbs_down']}")
            print(f"😐 No feedback: {metrics['no_feedback']}")
            print(f"📊 Engagement rate: {engagement_rate:.1%} (users who provided feedback)")
            print(f"📈 Satisfaction rate: {satisfaction_rate:.1%} (positive feedback rate)")
            print(f"🎯 Success thresholds: 60% satisfaction + 30% engagement")

            engagement_success = engagement_rate >= 0.3
            satisfaction_success = satisfaction_rate >= 0.6
            overall_success = engagement_success and satisfaction_success

            print(f"✅ Engagement: {'PASS' if engagement_success else 'FAIL'} ({engagement_rate:.1%})")
            print(f"✅ Satisfaction: {'PASS' if satisfaction_success else 'FAIL'} ({satisfaction_rate:.1%})")
            print(f"🏆 Overall: {'SUCCESS' if overall_success else 'NEEDS IMPROVEMENT'}")
        else:
            print("❌ No valid responses collected")
        print("=" * 60)

def main():
    parser = argparse.ArgumentParser(description='Generate traffic with 3-option feedback simulation')
    parser.add_argument('--queries', type=int, default=50,
                       help='Number of queries to generate (default: 50)')
    parser.add_argument('--delay', type=float, default=2.0,
                       help='Delay between API calls in seconds (default: 2.0)')

    args = parser.parse_args()

    # Validate arguments
    if args.queries <= 0:
        print("❌ Error: queries must be a positive integer")
        return

    if args.delay < 0:
        print("❌ Error: delay must be non-negative")
        return

    # Run the generator
    generator = DynamicExperimentGenerator()
    generator.run_experiment_generation(args.queries, args.delay)

if __name__ == "__main__":
    main()