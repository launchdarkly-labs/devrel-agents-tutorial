#!/usr/bin/env python3
"""
LaunchDarkly Multi-Agent Bootstrap Script
Creates segments, AI configs, and targeting rules for advanced deployment.
"""

import os
import yaml
import requests
import time
from pathlib import Path
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# The LaunchDarkly API rate-limits bursts of writes; wait and retry instead of skipping the call.
http = requests.Session()
http.mount("https://", HTTPAdapter(max_retries=Retry(
    total=5, backoff_factor=2, status_forcelist=[429], allowed_methods=None, raise_on_status=False)))

# JSON schemas for the tools in ai_config_manifest.yaml, matching the tutorials
TOOL_SCHEMAS = {
    "search_v1": {
        "type": "object",
        "properties": {
            "query": {"description": "Search query for keyword matching", "type": "string"},
            "top_k": {"description": "Number of results to return", "type": "number"}
        },
        "additionalProperties": False,
        "required": ["query"]
    },
    "search_v2": {
        "type": "object",
        "properties": {
            "query": {"description": "Search query for semantic matching", "type": "string"},
            "top_k": {"description": "Number of results to return", "type": "number"}
        },
        "additionalProperties": False,
        "required": ["query"]
    },
    "reranking": {
        "type": "object",
        "properties": {
            "query": {"description": "Original query for scoring", "type": "string"},
            "results": {"description": "Results to rerank", "type": "array"}
        },
        "additionalProperties": False,
        "required": ["query", "results"]
    },
    "arxiv_search": {
        "type": "object",
        "properties": {
            "query": {"description": "Search query for academic papers", "type": "string"},
            "max_results": {"description": "Maximum number of papers to return", "type": "number"}
        },
        "additionalProperties": False,
        "required": ["query"]
    },
    "openalex_search": {
        "type": "object",
        "properties": {
            "query": {"description": "Search query for scholarly works", "type": "string"}
        },
        "additionalProperties": False,
        "required": ["query"]
    },
}

class MultiAgentBootstrap:
    def __init__(self, api_key, base_url="https://app.launchdarkly.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": api_key,
            "LD-API-Version": "beta",
            "Content-Type": "application/json"
        }

    def create_segment(self, project_key, segment_data):
        """Create user segment for targeting using two-step process"""
        url = f"{self.base_url}/api/v2/segments/{project_key}/production"

        # Step 1: Create empty segment (LaunchDarkly ignores rules in POST)
        payload = {
            "key": segment_data["key"],
            "name": segment_data["key"].replace("-", " ").title()
        }

        response = http.post(url, headers=self.headers, json=payload, timeout=30)

        if response.status_code in [200, 201]:
            print(f"✅ Empty segment '{segment_data['key']}' created")
            time.sleep(0.5)
        elif response.status_code == 409:
            print(f"⚠️  Segment '{segment_data['key']}' already exists, adding rules...")
        else:
            print(f"❌ Failed to create segment: {response.text}")
            return None

        # Step 2: Add rules via semantic patch
        return self.add_segment_rules(project_key, segment_data)

    def add_segment_rules(self, project_key, segment_data):
        """Add rules to existing segment using semantic patch"""
        segment_key = segment_data["key"]
        url = f"{self.base_url}/api/v2/segments/{project_key}/production/{segment_key}"

        # Each segment should have one rule with multiple clauses
        instructions = []
        if segment_data.get("rules"):
            clauses = []
            for clause in segment_data["rules"]:
                clauses.append({
                    "attribute": clause["attribute"],
                    "op": clause["op"],
                    "values": clause["values"],
                    "contextKind": clause["contextKind"],
                    "negate": clause["negate"]
                })

            instructions.append({
                "kind": "addRule",
                "clauses": clauses
            })

        payload = {
            "environmentKey": "production",
            "instructions": instructions
        }

        print(f"  🔧 Adding {len(instructions)} rules to segment '{segment_key}'")

        # Use semantic patch headers for segment rule updates
        patch_headers = self.headers.copy()
        patch_headers["Content-Type"] = "application/json; domain-model=launchdarkly.semanticpatch"

        response = http.patch(url, headers=patch_headers, json=payload, timeout=30)

        if response.status_code == 200:
            result = response.json()
            rules_count = len(result.get("rules", []))
            print(f"  ✅ Rules added to segment '{segment_key}' (final count: {rules_count})")
            time.sleep(0.5)
            return result
        else:
            print(f"  ❌ Failed to add rules to segment '{segment_key}': {response.text}")
            return None

    def create_variation(self, project_key, config_key, variation_data):
        """Create AI Config variation"""
        url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs/{config_key}/variations"

        model_config = variation_data["modelConfig"]
        model_id = model_config["modelId"]

        # Map to correct LaunchDarkly model config keys and canonical provider names
        model_config_key_map = {
            "claude-sonnet-5-5": "Anthropic.claude-sonnet-5-5",
            "claude-haiku-5-5": "Anthropic.claude-haiku-5-5",
            "claude-opus-5-5": "Anthropic.claude-opus-5-5",
            "gpt-6.2-sol": "OpenAI.gpt-6.2-sol",
            "gpt-6.1-terra": "OpenAI.gpt-6.1-terra",
            "gpt-6-luna": "OpenAI.gpt-6-luna",
            "mistral-small-latest": "Mistral.mistral-small-latest"
        }
        provider_name_map = {
            "anthropic": "Anthropic",
            "bedrock": "Bedrock",
            "cohere": "Cohere",
            "deepseek": "DeepSeek",
            "gemini": "Gemini",
            "google": "Google",
            "meta": "Meta",
            "mistral": "Mistral",
            "openai": "OpenAI",
            "perplexity": "Perplexity",
            "xai": "xAI",
        }
        model_config_key = model_config_key_map.get(model_id)

        payload = {
            "key": variation_data["key"],
            "name": variation_data.get("name", variation_data["key"].replace("-", " ").title()),
            "messages": [],  # Empty array required for agent mode validation
            "instructions": variation_data["instructions"],
            "tools": [{"key": tool, "version": 1} for tool in variation_data.get("tools", [])]
        }

        # Custom parameters such as max_tool_calls live in the variation's model.custom
        if variation_data.get("customParameters"):
            payload["model"] = {"custom": variation_data["customParameters"]}

        # Use modelConfigKey if we have it, otherwise fallback to modelName/provider
        if model_config_key:
            payload["modelConfigKey"] = model_config_key
            print(f"  🔧 Using modelConfigKey: {model_config_key}")
        else:
            raw_provider = model_config["provider"]
            provider_name = provider_name_map.get(raw_provider.lower(), raw_provider)
            payload["modelName"] = model_id
            payload["provider"] = {"name": provider_name}
            print(f"  🔧 Using modelName/provider fallback: {model_id}/{provider_name}")

        response = http.post(url, headers=self.headers, json=payload, timeout=30)

        if response.status_code in [200, 201]:
            print(f"  ✅ Variation '{variation_data['key']}' created")
            time.sleep(0.5)
            return response.json()
        elif response.status_code == 409:
            # Already exists; this script is add-only
            return None
        else:
            print(f"  ❌ Failed to create variation: {response.text}")
            return None

    def create_tool(self, project_key, tool_data):
        """Create tool for AI Configs using correct API endpoint"""
        url = f"{self.base_url}/api/v2/projects/{project_key}/ai-tools"

        schema = TOOL_SCHEMAS.get(
            tool_data["key"],
            {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
        )

        payload = {
            "key": tool_data["key"],
            "name": tool_data["name"],
            "description": tool_data["description"],
            "schema": schema
        }

        # Add MCP-specific configuration if applicable
        if tool_data.get("type") == "mcp":
            payload["mcpServer"] = tool_data.get("server", "")
            payload["type"] = "mcp"
        else:
            payload["type"] = "function"

        response = http.post(url, headers=self.headers, json=payload, timeout=30)

        if response.status_code in [200, 201]:
            print(f"  ✅ Tool '{tool_data['key']}' created")
            time.sleep(0.5)
            return response.json()
        elif response.status_code == 409:
            return None
        else:
            print(f"  ❌ Failed to create tool: {response.text}")
            return None

    def get_targeting_variation_map(self, project_key, config_key):
        """Get targeting variation IDs (different from AI config variation IDs)"""
        url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs/{config_key}/targeting"
        response = http.get(url, headers=self.headers, timeout=30)

        if response.status_code != 200:
            print(f"❌ Failed to fetch targeting data: {response.text}")
            return {}

        variation_map = {}
        for variation in response.json().get("variations", []):
            # Skip the "disabled" variation
            if variation.get("name") == "disabled":
                continue

            # Extract variation key from the value._ldMeta.variationKey field
            variation_key = variation.get("value", {}).get("_ldMeta", {}).get("variationKey")
            if variation_key:
                variation_map[variation_key] = variation["_id"]

        return variation_map

    def ensure_ai_config_exists(self, project_key, config_data):
        """Check that an AI Config exists. Part 1 creates them, so this script never does."""
        config_key = config_data["key"]
        url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs/{config_key}"
        response = http.get(url, headers=self.headers, timeout=30)
        if response.status_code == 200:
            print(f"✅ AI Config '{config_key}' exists")
            return True
        print(f"⚠️  AI Config '{config_key}' not found. Skipping creation.")
        return False

    def update_targeting(self, project_key, config_key, targeting_data):
        """Update AI Config targeting rules using correct agent mode format"""
        # First get the targeting variation IDs
        targeting_variation_map = self.get_targeting_variation_map(project_key, config_key)
        if not targeting_variation_map:
            print(f"❌ Could not get targeting variation map for '{config_key}'")
            return None

        print(f"📊 Available targeting variations for '{config_key}': {list(targeting_variation_map.keys())}")

        url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs/{config_key}/targeting"

        instructions = []

        # Add segment-based rules
        for rule in targeting_data["rules"]:
            variation_key = rule["variation"]
            targeting_variation_id = targeting_variation_map.get(variation_key)

            if not targeting_variation_id:
                print(f"⚠️  Variation '{variation_key}' not found in targeting variations")
                continue

            # Create add rule instruction for each segment
            for segment in rule["segments"]:
                instruction = {
                    "kind": "addRule",
                    "clauses": [
                        {
                            "attribute": "segmentMatch",
                            "op": "segmentMatch",
                            "values": [segment],
                            "contextKind": "user"
                        }
                    ],
                    "variationId": targeting_variation_id
                }
                instructions.append(instruction)
                print(f"  ✅ Added rule: segment '{segment}' -> variation '{variation_key}'")

        # Set fallthrough variation
        fallthrough_variation_key = targeting_data["defaultVariation"]
        fallthrough_variation_id = targeting_variation_map.get(fallthrough_variation_key)

        if fallthrough_variation_id:
            instructions.append({
                "kind": "updateFallthroughVariationOrRollout",
                "variationId": fallthrough_variation_id
            })
            print(f"  ✅ Set fallthrough to variation '{fallthrough_variation_key}'")
        else:
            print(f"⚠️  Fallthrough variation '{fallthrough_variation_key}' not found")

        payload = {
            "environmentKey": "production",
            "instructions": instructions
        }

        response = http.patch(url, headers=self.headers, json=payload, timeout=30)

        if response.status_code == 200:
            print(f"✅ Targeting rules updated for '{config_key}'")
            return response.json()
        else:
            print(f"❌ Failed to update targeting: {response.text}")
            return None

def main():
    load_dotenv()

    print("🚀 LaunchDarkly AI Config Bootstrap")
    print("=" * 50)
    print("⚠️  IMPORTANT: This script is for INITIAL SETUP ONLY")
    print("📝 After bootstrap completes:")
    print("   • Make ALL configuration changes in LaunchDarkly UI")
    print("   • Do NOT modify ai_config_manifest.yaml")
    print("   • LaunchDarkly is your single source of truth")
    print("=" * 50)
    print()

    api_key = os.getenv("LD_API_KEY")
    if not api_key:
        print("❌ LD_API_KEY environment variable not set")
        print("   Get your API key from: https://app.launchdarkly.com/settings/authorization")
        return

    # Load manifest
    manifest_path = Path(__file__).parent / "ai_config_manifest.yaml"
    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    project_key = os.getenv("LD_PROJECT_KEY") or manifest["project"]["key"]
    bootstrap = MultiAgentBootstrap(api_key)

    print("🚀 Starting multi-agent system bootstrap (add-only)...")
    print(f"📦 Project: {project_key}")
    print()

    # 1) Tools (search_v2 and reranking were created in Part 1)
    print("🔧 Creating tools...")
    part1_tool_keys = {"search_v2", "reranking"}
    for tool in manifest["project"]["tool"]:
        if tool["key"] not in part1_tool_keys:
            bootstrap.create_tool(project_key, tool)
    print()

    # 2) AI Configs (ensure they exist from Part 1)
    print("🤖 Ensuring AI configs exist...")
    existing_config_keys = set()
    for ai_config in manifest["project"]["ai_config"]:
        if bootstrap.ensure_ai_config_exists(project_key, ai_config):
            existing_config_keys.add(ai_config["key"])
    if not existing_config_keys:
        print("⚠️  No existing AI configs found. This script assumes Part 1 created base configs. Skipping variations/targeting.")
    print()

    # 3) Variations (add-only; skip if exists)
    print("🧩 Creating variations...")
    skip_variations = {"supervisor-basic"}  # Created in Part 1
    for ai_config in manifest["project"]["ai_config"]:
        if ai_config["key"] not in existing_config_keys:
            continue
        for variation in ai_config.get("variations", []):
            if variation["key"] not in skip_variations:
                bootstrap.create_variation(project_key, ai_config["key"], variation)
    print()

    # 4) Segments (required for targeting rules)
    print("📦 Creating segments (for targeting rules)...")
    for segment in manifest["project"]["segment"]:
        bootstrap.create_segment(project_key, segment)
    print()

    # 5) Targeting
    print("🎯 Updating targeting rules...")
    for ai_config in manifest["project"]["ai_config"]:
        config_key = ai_config["key"]
        if config_key not in existing_config_keys:
            continue
        if ai_config["targeting"].get("rules"):
            bootstrap.update_targeting(project_key, config_key, ai_config["targeting"])
        else:
            print(f"  ⏭️  Skipping targeting for '{config_key}' (empty rules)")
    print()

    print("✨ Bootstrap complete!")
    print()
    print("🎯 Next steps:")
    print("   1. Check your LaunchDarkly dashboard to verify configurations")
    print("   2. Test different user contexts with the demo")
    print("   3. Monitor usage patterns and adjust targeting rules")
    print()
    print("🔄 IMPORTANT REMINDER:")
    print("   • Future changes: Use LaunchDarkly UI only")
    print("   • Instructions: Modify in LaunchDarkly, not YAML")
    print("   • Targeting: Update in LaunchDarkly dashboard")
    print("   • This YAML file is now a historical record")

if __name__ == "__main__":
    main()
