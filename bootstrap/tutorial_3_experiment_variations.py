#!/usr/bin/env python3
"""
Bootstrap script for Tutorial 3 Experiment Variations

Creates the 4 experiment variations needed for tutorial-3 A/B testing:
- Tool Implementation ROI: Which tool configuration delivers the best satisfaction while maintaining acceptable cost and latency trade-offs?
- Model Efficiency Analysis: Does Claude Opus 4 deliver superior user satisfaction compared to GPT-4o for premium users?

This script is separate from the tutorial-2 bootstrap and only handles
experiment variations, not the base AI Configs (which should already exist).
"""

import os
import sys
import time
from typing import Dict, Any, List
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Tutorial3VariationBootstrap:
    def __init__(self):
        self.api_key = os.getenv('LD_API_KEY')
        self.project_key = "multi-agent-chatbot"
        self.base_url = "https://app.launchdarkly.com/api/v2"

        if not self.api_key:
            print("❌ Error: LD_API_KEY not found in environment variables")
            print("   Get your API key from LaunchDarkly: Account Settings → API Access Tokens")
            sys.exit(1)

        self.headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
            "LD-API-Version": "beta"
        }

    def create_tool_implementation_variations(self) -> bool:
        """Create the 4 variations for tool implementation ROI experiment"""

        variations = [
            {
                "key": "control-basic",
                "name": "Control - Basic Search",
                "instructions": "You are a helpful assistant that can search documentation and research papers. When search results are available, prioritize information from those results over your general knowledge to provide the most accurate and up-to-date responses.",
                "model": {
                    "name": "claude-3-5-sonnet-20241022",
                    "provider": "anthropic"
                },
                "tools": ["search_v1"],
                "customParameters": {}
            },
            {
                "key": "treatment-a-advanced",
                "name": "Treatment A - Advanced Internal",
                "instructions": "You are a helpful assistant that can search documentation and research papers. When search results are available, prioritize information from those results over your general knowledge to provide the most accurate and up-to-date responses. Use available tools to search the knowledge base accurately and comprehensively.",
                "model": {
                    "name": "claude-3-5-sonnet-20241022",
                    "provider": "anthropic"
                },
                "tools": ["search_v2", "reranking"],
                "customParameters": {}
            },
            {
                "key": "treatment-c-external",
                "name": "Treatment C - External Only",
                "instructions": "You are a helpful assistant that can search external research databases. Use available tools to search academic databases to answer questions accurately and comprehensively with the latest research.",
                "model": {
                    "name": "claude-3-5-sonnet-20241022",
                    "provider": "anthropic"
                },
                "tools": ["arxiv_search", "semantic_scholar"],
                "customParameters": {"max_tool_calls": 8}
            }
        ]

        return self._create_variations("support-agent", variations)

    def create_model_efficiency_variations(self) -> bool:
        """Create the 1 premium model variation for model efficiency experiment"""

        variations = [
            {
                "key": "claude-opus-treatment",
                "name": "Claude Opus 4 Treatment",
                "instructions": "You are a helpful assistant that can search documentation and research papers. When search results are available, prioritize information from those results over your general knowledge to provide the most accurate and up-to-date responses. Use available tools to search the knowledge base and external research databases to answer questions accurately and comprehensively.",
                "model": {
                    "name": "claude-opus-4-20250514",
                    "provider": "anthropic"
                },
                "tools": ["search_v1", "search_v2", "reranking", "arxiv_search", "semantic_scholar"],
                "customParameters": {"max_tool_calls": 10}
            }
        ]

        return self._create_variations("support-agent", variations)

    def _create_variations(self, ai_config_key: str, variations: List[Dict[str, Any]]) -> bool:
        """Create variations for a specific AI Config"""

        print(f"\n📝 Creating {len(variations)} variations for {ai_config_key}...")

        for variation in variations:
            url = f"{self.base_url}/projects/{self.project_key}/ai-configs/{ai_config_key}/variations"

            payload = {
                "key": variation["key"],
                "name": variation["name"],
                "messages": [],  # Empty array required for agent mode validation
                "instructions": variation["instructions"],
                "tools": [{"key": tool, "version": 1} for tool in variation["tools"]],
                "modelName": variation["model"]["name"],
                "provider": {"name": variation["model"]["provider"]}
            }

            # Add custom parameters if they exist
            if variation["customParameters"]:
                payload.update(variation["customParameters"])

            try:
                response = requests.post(url, json=payload, headers=self.headers)

                if response.status_code == 201:
                    print(f"  ✅ Created variation: {variation['key']}")
                elif response.status_code == 409:
                    print(f"  ⚠️  Variation already exists: {variation['key']}")
                else:
                    print(f"  ❌ Failed to create {variation['key']}: {response.status_code}")
                    print(f"     Response: {response.text}")
                    return False

                # Small delay to avoid rate limiting
                time.sleep(0.5)

            except Exception as e:
                print(f"  ❌ Error creating {variation['key']}: {str(e)}")
                return False

        return True

    def verify_prerequisites(self) -> bool:
        """Verify that required AI Configs and tools exist"""

        print("🔍 Verifying prerequisites...")

        # Check if support-agent AI Config exists
        url = f"{self.base_url}/projects/{self.project_key}/ai-configs/support-agent"
        response = requests.get(url, headers=self.headers)

        if response.status_code != 200:
            print(f"❌ Error: support-agent AI Config not found (status: {response.status_code})")
            print(f"   Response: {response.text}")
            print("   Please complete tutorial-2 first to create the base AI Configs")
            return False

        print("  ✅ support-agent AI Config exists")

        # Check if required tools exist
        required_tools = ["search_v1", "search_v2", "reranking", "arxiv_search", "semantic_scholar"]
        tools_url = f"{self.base_url}/projects/{self.project_key}/ai-configs/tools"
        tools_response = requests.get(tools_url, headers=self.headers)

        if tools_response.status_code == 200:
            existing_tools = [tool["key"] for tool in tools_response.json().get("items", [])]
            missing_tools = [tool for tool in required_tools if tool not in existing_tools]

            if missing_tools:
                print(f"❌ Error: Missing required tools: {missing_tools}")
                print("   Please create these tools in LaunchDarkly Library → Tools")
                return False

            print("  ✅ All required tools exist")
        else:
            print("⚠️  Warning: Could not verify tools (continuing anyway)")

        return True

    def run(self):
        """Main execution method"""

        print("🚀 Tutorial 3 Experiment Variations Bootstrap")
        print("=" * 50)

        if not self.verify_prerequisites():
            sys.exit(1)

        print("\n📋 Creating experiment variations...")

        # Create tool implementation variations
        if not self.create_tool_implementation_variations():
            print("❌ Failed to create tool implementation variations")
            sys.exit(1)

        # Create model efficiency variations
        if not self.create_model_efficiency_variations():
            print("❌ Failed to create model efficiency variations")
            sys.exit(1)

        print("\n" + "=" * 50)
        print("✅ SUCCESS: All experiment variations created!")
        print("\nNext steps:")
        print("1. Go to LaunchDarkly AI Configs → support-agent")
        print("2. Create experiments using these variations")
        print("3. Follow tutorial-3 for metrics and experiment setup")
        print("\nCreated variations:")
        print("  Tool Implementation: control-basic, treatment-a-advanced, treatment-c-external")
        print("  Model Efficiency: claude-opus-treatment")
        print("  Note: Remaining variations use existing other-paid configuration")

if __name__ == "__main__":
    bootstrap = Tutorial3VariationBootstrap()
    bootstrap.run()