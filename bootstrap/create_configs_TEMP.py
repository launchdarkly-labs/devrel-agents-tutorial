#!/usr/bin/env python3
"""
LaunchDarkly Multi-Agent Bootstrap Script
Creates segments, AI configs, and targeting rules for advanced deployment.
"""

import os
import yaml
import requests
import json
import time
from pathlib import Path
from dotenv import load_dotenv

class MultiAgentBootstrap:
    def __init__(self, api_key, base_url="https://app.launchdarkly.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.overwrite = False
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
            "name": segment_data["key"]
        }
        
        response = requests.post(url, headers=self.headers, json=payload, timeout=30)
        
        if response.status_code in [200, 201]:
            print(f" Empty segment '{segment_data['key']}' created")
            time.sleep(0.5)
            
            # Step 2: Add rules via semantic patch
            return self.add_segment_rules(project_key, segment_data)
            
        elif response.status_code == 409:
            if self.overwrite:
                print(f"  Segment '{segment_data['key']}' already exists, deleting and recreating...")
                # Delete existing segment
                delete_url = f"{self.base_url}/api/v2/segments/{project_key}/production/{segment_data['key']}"
                delete_response = requests.delete(delete_url, headers=self.headers, timeout=30)
                
                if delete_response.status_code == 204:
                    print(f"🗑️  Deleted existing segment '{segment_data['key']}'")
                    time.sleep(1)  # Wait for deletion to propagate
                    # Retry creation
                    retry_response = requests.post(url, headers=self.headers, json=payload, timeout=30)
                    if retry_response.status_code in [200, 201]:
                        print(f" Empty segment '{segment_data['key']}' recreated")
                        time.sleep(0.5)
                        # Step 2: Add rules via semantic patch
                        return self.add_segment_rules(project_key, segment_data)
                    else:
                        print(f" Failed to recreate segment: {retry_response.text}")
                        return None
                else:
                    print(f" Failed to delete existing segment: {delete_response.text}")
                    return None
            else:
                print(f"  Segment '{segment_data['key']}' already exists, adding rules...")
                return self.add_segment_rules(project_key, segment_data)
        else:
            print(f" Failed to create segment: {response.text}")
            return None
    
    def add_segment_rules(self, project_key, segment_data):
        """Add rules to existing segment using semantic patch"""
        segment_key = segment_data["key"]
        url = f"{self.base_url}/api/v2/segments/{project_key}/production/{segment_key}"
        
        # Build instructions for semantic patch
        instructions = []
        
        # Each segment should have one rule with multiple clauses
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
        
        print(f"   Adding {len(instructions)} rules to segment '{segment_key}'")
        
        # Use semantic patch headers for segment rule updates
        patch_headers = self.headers.copy()
        patch_headers["Content-Type"] = "application/json; domain-model=launchdarkly.semanticpatch"
        
        response = requests.patch(url, headers=patch_headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            rules_count = len(result.get("rules", []))
            print(f"   Rules added to segment '{segment_key}' (final count: {rules_count})")
            time.sleep(0.5)
            return result
        else:
            print(f"   Failed to add rules to segment '{segment_key}': {response.text}")
            return None
    
    def create_ai_config(self, project_key, config_data):
        """Add variations to existing AI Config or create if not exists"""
        config_key = config_data['key']
        
        # Check if config already exists
        check_url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs/{config_key}"
        check_response = requests.get(check_url, headers=self.headers, timeout=30)
        
        if check_response.status_code == 200:
            print(f" AI Config '{config_key}' exists, adding variations")
            config_exists = True
        else:
            print(f"  AI Config '{config_key}' not found, skipping creation")
            return None
        
        # If overwrite mode, clear all targeting rules first to allow variation deletion/recreation
        if self.overwrite:
            print(f"  🔄 Overwrite mode: Clearing targeting rules for '{config_key}'...")
            self.delete_all_targeting_rules(project_key, config_key)
        
        # Add variations to existing config
        for variation in config_data["variations"]:
            self.create_variation(project_key, config_key, variation)
        
        # Set up targeting (always update, regardless of overwrite mode)
        if "targeting" in config_data:
            self.update_targeting(project_key, config_key, config_data["targeting"])
        
        return {"key": config_key, "status": "updated"}
    
    def delete_variation_if_exists(self, project_key, config_key, variation_key):
        """Delete a specific variation if it exists"""
        variations = self.list_variations(project_key, config_key)
        # Debug: Show all available variation keys
        available_keys = [v.get("key") or v.get("variationKey", "unknown") for v in variations]
        print(f"     Debug: Looking for '{variation_key}' in available variations: {available_keys}")
        
        # Find the variation by key
        variation_id = None
        for variation in variations:
            v_key = variation.get("key") or variation.get("variationKey")
            if v_key == variation_key:
                variation_id = variation.get("_id") or variation.get("id")
                break
                
        if not variation_id:
            print(f"    ℹ️  Variation '{variation_key}' not found in AI config")
            return False
        
        # Delete the variation
        delete_url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs/{config_key}/variations/{variation_id}"
        delete_response = requests.delete(delete_url, headers=self.headers, timeout=30)
        
        if delete_response.status_code == 204:
            print(f"    🗑️  Deleted existing variation '{variation_key}'")
            time.sleep(0.5)  # Rate limiting delay
            return True
        else:
            print(f"      Failed to delete variation '{variation_key}': {delete_response.status_code}")
            return False
    
    def create_variation(self, project_key, config_key, variation_data):
        """Create AI Config variation"""
        variation_key = variation_data["key"]
        
        # If overwrite mode, delete existing variation first
        if self.overwrite:
            self.delete_variation_if_exists(project_key, config_key, variation_key)
        
        url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs/{config_key}/variations"
        
        # Map model IDs to correct modelConfigKey values
        model_config = variation_data["modelConfig"]
        model_id = model_config["modelId"]
        provider = model_config["provider"].lower()
        
        # Map to correct LaunchDarkly model config keys
        model_config_key_map = {
            "claude-3-5-sonnet-20241022": "Anthropic.claude-3-7-sonnet-latest",
            "claude-3-5-haiku-20241022": "Anthropic.claude-3-5-haiku-20241022",
            "claude-opus-4-20250514": "Anthropic.claude-opus-4-20250514",
            "gpt-4o": "OpenAI.gpt-4o",
            "gpt-4o-mini": "OpenAI.gpt-4o-mini-2024-07-18",
            "mistral-small-latest": "Mistral.mistral-small-latest"
        }
        
        model_config_key = model_config_key_map.get(model_id)
        if not model_config_key:
            print(f"    Unknown model ID '{model_id}', using fallback approach")
            # Fallback to original approach
            model_config_key = None
        
        payload = {
            "key": variation_data["key"],
            "name": variation_data.get("name", variation_data["key"].replace("-", " ").title()),
            "messages": [],  # Empty array required for agent mode validation
            "instructions": variation_data["instructions"],
            "tools": [{"key": tool, "version": 1} for tool in variation_data.get("tools", [])]
        }
        
        # Use modelConfigKey if we have it, otherwise fallback to modelName/provider
        if model_config_key:
            payload["modelConfigKey"] = model_config_key
            print(f"   Using modelConfigKey: {model_config_key}")
        else:
            payload["modelName"] = model_id
            payload["provider"] = {"name": model_config["provider"].title()}
            print(f"   Using modelName/provider fallback: {model_id}/{provider}")
        
        print(f"DEBUG: Sending payload: {json.dumps(payload, indent=2)}")
        response = requests.post(url, headers=self.headers, json=payload, timeout=30)
        
        if response.status_code in [200, 201]:
            print(f"   Variation '{variation_data['key']}' created")
            time.sleep(0.5)
            return response.json()
        elif response.status_code == 409:
            if self.overwrite:
                return self.update_variation(project_key, config_key, variation_data)
            else:
                return None
        else:
            print(f"   Failed to create variation: {response.text}")
            return None
    
    def update_variation(self, project_key, config_key, variation_data):
        """Update existing AI Config variation using variations endpoint IDs."""
        variation_key = variation_data["key"]
        variations = self.list_variations(project_key, config_key)
        variation_id = None
        for variation in variations:
            v_key = variation.get("key") or variation.get("variationKey")
            if v_key == variation_key:
                variation_id = variation.get("_id") or variation.get("id")
                break
        
        if not variation_id:
            print(f"     Could not resolve variation ID for '{variation_key}' via variations endpoint")
            return None
        
        # Use the AI config variation ID with the regular AI config variations endpoint
        url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs/{config_key}/variations/{variation_id}"
        
        # Build the same payload as create with model config key mapping
        model_config = variation_data["modelConfig"]
        model_id = model_config["modelId"]
        
        # Map to correct LaunchDarkly model config keys
        model_config_key_map = {
            "claude-3-5-sonnet-20241022": "Anthropic.claude-3-7-sonnet-latest",
            "claude-3-5-haiku-20241022": "Anthropic.claude-3-5-haiku-20241022",
            "claude-opus-4-20250514": "Anthropic.claude-opus-4-20250514",
            "gpt-4o": "OpenAI.gpt-4o",
            "gpt-4o-mini": "OpenAI.gpt-4o-mini-2024-07-18",
            "mistral-small-latest": "Mistral.mistral-small-latest"
        }
        
        model_config_key = model_config_key_map.get(model_id)
        
        payload = {
            "instructions": variation_data["instructions"],
            "tools": [{"key": tool, "version": 1} for tool in variation_data.get("tools", [])]
        }
        
        # Use modelConfigKey if we have it, otherwise fallback to modelName/provider
        if model_config_key:
            payload["modelConfigKey"] = model_config_key
            print(f"     Updating with modelConfigKey: {model_config_key}")
        else:
            payload["modelName"] = model_id
            payload["provider"] = {"name": model_config["provider"].title()}
            print(f"     Updating with modelName/provider fallback: {model_id}")
        
        response = requests.patch(url, headers=self.headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            print(f"     Variation '{variation_data['key']}' updated")
            time.sleep(0.5)
            return response.json()
        else:
            print(f"     Failed to update variation: {response.text}")
            return None
    
    def create_tool(self, project_key, tool_data):
        """Create tool for AI Configs using correct API endpoint"""
        tool_key = tool_data["key"]
        
        # Note: Tool deletion is handled in the main cleanup flow due to dependencies
        # Tools can't be deleted while variations still reference them
        
        url = f"{self.base_url}/api/v2/projects/{project_key}/ai-tools"
        
        # Build schema per tool key based on tutorial_2.md and README
        schema = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
        if tool_key == "search_v1":
            schema = {
                "type": "object",
                "properties": {
                    "query": {
                        "description": "Search query for keyword matching",
                        "type": "string"
                    },
                    "top_k": {
                        "description": "Number of results to return",
                        "type": "number"
                    }
                },
                "additionalProperties": False,
                "required": ["query"]
            }
        elif tool_key == "search_v2":
            schema = {
                "type": "object",
                "properties": {
                    "query": {
                        "description": "Search query for semantic matching",
                        "type": "string"
                    },
                    "top_k": {
                        "description": "Number of results to return",
                        "type": "number"
                    }
                },
                "additionalProperties": False,
                "required": ["query"]
            }
        elif tool_key == "reranking":
            schema = {
                "type": "object",
                "properties": {
                    "query": {
                        "description": "Original query for scoring",
                        "type": "string"
                    },
                    "results": {
                        "description": "Results to rerank",
                        "type": "array"
                    }
                },
                "additionalProperties": False,
                "required": ["query", "results"]
            }
        elif tool_key == "arxiv_search":
            schema = {
                "type": "object",
                "properties": {
                    "query": {
                        "description": "Search query for academic papers",
                        "type": "string"
                    },
                    "max_results": {
                        "description": "Maximum number of papers to return",
                        "type": "number"
                    }
                },
                "additionalProperties": False,
                "required": ["query"]
            }
        elif tool_key == "semantic_scholar":
            schema = {
                "type": "object",
                "properties": {
                    "query": {
                        "description": "Search query for citation data",
                        "type": "string"
                    },
                    "fields": {
                        "description": "Fields to return from papers",
                        "type": "array"
                    }
                },
                "additionalProperties": False,
                "required": ["query"]
            }

        payload = {
            "key": tool_data["key"],
            "name": tool_data["name"],
            "description": tool_data["description"],
            "schema": schema
        }
        
        # Add MCP-specific configuration if applicable
        if tool_data.get("type") == "mcp":
            payload["mcpServer"] = tool_data.get("server", "")
            # MCP tools may have different schema requirements
            payload["type"] = "mcp"
        else:
            payload["type"] = "function"
        
        print(f"   Creating tool with payload: {json.dumps(payload, indent=2)}")
        response = requests.post(url, headers=self.headers, json=payload, timeout=30)
        
        if response.status_code in [200, 201]:
            print(f"   Tool '{tool_data['key']}' created")
            time.sleep(0.5)
            return response.json()
        elif response.status_code == 409:
            return None
        else:
            print(f"   Failed to create tool: {response.text}")
            try:
                error_detail = response.json()
                print(f"      Error details: {json.dumps(error_detail, indent=2)}")
            except:
                pass
            return None

    def delete_tool(self, project_key, tool_key):
        """Delete tool from project"""
        url = f"{self.base_url}/api/v2/projects/{project_key}/ai-tools/{tool_key}"
        
        response = requests.delete(url, headers=self.headers, timeout=30)
        
        if response.status_code == 204:
            print(f"  🗑️  Tool '{tool_key}' deleted")
            time.sleep(0.5)
            return True
        elif response.status_code == 404:
            print(f"  ℹ️  Tool '{tool_key}' not found (may already be deleted)")
            return True
        else:
            print(f"   Failed to delete tool '{tool_key}': {response.text}")
            return False
    
    def delete_all_targeting_rules(self, project_key, config_key):
        """Clear all targeting rules by setting everything to 'disabled' variation"""
        url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs/{config_key}/targeting"
        
        # Get current targeting to understand existing rules and find disabled variation
        response = requests.get(url, headers=self.headers, timeout=30)
        if response.status_code != 200:
            print(f"    Could not fetch targeting for '{config_key}'")
            return False
            
        targeting_data = response.json()
        rules = targeting_data.get("rules", [])
        variations = targeting_data.get("variations", [])
        
        # Debug: Print current targeting state
        print(f"   Debug: '{config_key}' has {len(rules)} rules and {len(variations)} variations")
        if rules:
            rule_info = [f'rule-{i}: segments={rule.get("clauses", [])}' for i, rule in enumerate(rules)]
            print(f"      Rules: {rule_info}")
        
        # Find the "disabled" variation ID
        disabled_variation_id = None
        for variation in variations:
            if variation.get("name") == "disabled":
                disabled_variation_id = variation["_id"]
                break
                
        if not disabled_variation_id:
            print(f"    Could not find 'disabled' variation for '{config_key}'")
            print(f"      Available variations: {[v.get('name', 'unknown') for v in variations]}")
            return False
        
        if not rules:
            print(f"  ℹ️  No targeting rules to clear for '{config_key}'")
            return True
            
        # Create instructions to remove all rules and set fallthrough to disabled
        instructions = []
        
        # Remove all existing rules
        for rule in rules:
            instructions.append({
                "kind": "removeRule",
                "ruleId": rule["_id"]
            })
            
        # Set fallthrough to disabled variation
        instructions.append({
            "kind": "updateFallthroughVariationOrRollout",
            "variationId": disabled_variation_id
        })
            
        payload = {
            "environmentKey": "production", 
            "instructions": instructions
        }
        
        print(f"   Debug: Sending {len(instructions)} instructions to clear targeting")
        response = requests.patch(url, headers=self.headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            print(f"  🗑️  Cleared {len(rules)} targeting rules for '{config_key}' (set to disabled)")
            time.sleep(0.5)
            return True
        else:
            print(f"   Failed to clear targeting rules: {response.text}")
            return False

    def get_targeting_variation_map(self, project_key, config_key):
        """Get targeting variation IDs (different from AI config variation IDs)"""
        url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs/{config_key}/targeting"
        response = requests.get(url, headers=self.headers, timeout=30)
        
        if response.status_code == 200:
            targeting_data = response.json()
            targeting_variations = targeting_data.get("variations", [])
            
            variation_map = {}
            for variation in targeting_variations:
                # Skip the "disabled" variation
                if variation.get("name") == "disabled":
                    continue
                    
                # Extract variation key from the value._ldMeta.variationKey field
                variation_value = variation.get("value", {})
                ld_meta = variation_value.get("_ldMeta", {})
                variation_key = ld_meta.get("variationKey")
                
                if variation_key:
                    variation_map[variation_key] = variation["_id"]
                    
            return variation_map
        else:
            print(f" Failed to fetch targeting data: {response.text}")
            return {}

    def get_ai_config_variation_id_map(self, project_key, config_key):
        """Get AI config variation IDs from the AI config itself (key -> _id)."""
        url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs/{config_key}"
        response = requests.get(url, headers=self.headers, timeout=30)

        if response.status_code != 200:
            print(f" Failed to fetch AI config variations for '{config_key}': {response.text}")
            return {}

        config_data = response.json()
        variations = config_data.get("variations", [])
        return {v.get("key"): v.get("_id") for v in variations if v.get("key") and v.get("_id")}

    def list_variations(self, project_key, config_key):
        """List variations via the variations endpoint used for create/update/delete."""
        url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs/{config_key}/variations"
        response = requests.get(url, headers=self.headers, timeout=30)
        if response.status_code != 200:
            print(f"      Could not list variations for '{config_key}': {response.text}")
            return []
        try:
            data = response.json()
        except Exception:
            print("      Invalid JSON from variations list")
            return []
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data["items"]
        return []

    def update_variation_tools_only(self, project_key, config_key, variation_key, tools_list):
        """Update only the tools array for a specific variation (by key)."""
        variation_id_map = self.get_ai_config_variation_id_map(project_key, config_key)
        variation_id = variation_id_map.get(variation_key)
        if not variation_id:
            print(f"      Could not find variation id for '{variation_key}' while updating tools")
            return False

        url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs/{config_key}/variations/{variation_id}"
        payload = {
            "tools": [{"key": t, "version": 1} for t in (tools_list or [])]
        }

        response = requests.patch(url, headers=self.headers, json=payload, timeout=30)
        if response.status_code == 200:
            print(f"     Updated tools for variation '{variation_key}' → {tools_list or []}")
            time.sleep(0.2)
            return True
        else:
            print(f"     Failed updating tools for '{variation_key}': {response.text}")
            return False

    def ensure_ai_config_exists(self, project_key, config_data):
        """Ensure an AI Config exists; do not delete it in overwrite mode."""
        config_key = config_data["key"]
        url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs/{config_key}"
        response = requests.get(url, headers=self.headers, timeout=30)
        if response.status_code == 200:
            print(f" AI Config '{config_key}' exists")
            return True
        else:
            # For safety, we won't attempt to create brand-new configs here without a stable schema.
            print(f"  AI Config '{config_key}' not found. Skipping creation.")
            return False

    # Removed detachment logic per new overwrite deletion order requirements

    def update_targeting(self, project_key, config_key, targeting_data):
        """Update AI Config targeting rules using correct agent mode format"""
        # First get the targeting variation IDs
        targeting_variation_map = self.get_targeting_variation_map(project_key, config_key)
        if not targeting_variation_map:
            print(f" Could not get targeting variation map for '{config_key}'")
            return None
            
        print(f" Available targeting variations for '{config_key}': {list(targeting_variation_map.keys())}")
        
        url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs/{config_key}/targeting"
        
        instructions = []
        
        # Add segment-based rules
        for rule in targeting_data["rules"]:
            variation_key = rule["variation"]
            targeting_variation_id = targeting_variation_map.get(variation_key)
            
            if not targeting_variation_id:
                print(f"  Variation '{variation_key}' not found in targeting variations")
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
                print(f"   Added rule: segment '{segment}' -> variation '{variation_key}'")
        
        # Set fallthrough variation
        fallthrough_variation_key = targeting_data["defaultVariation"]
        fallthrough_variation_id = targeting_variation_map.get(fallthrough_variation_key)
        
        if fallthrough_variation_id:
            instructions.append({
                "kind": "updateFallthroughVariationOrRollout",
                "variationId": fallthrough_variation_id
            })
            print(f"   Set fallthrough to variation '{fallthrough_variation_key}'")
        else:
            print(f"  Fallthrough variation '{fallthrough_variation_key}' not found")
        
        payload = {
            "environmentKey": "production",
            "instructions": instructions
        }
        
        response = requests.patch(url, headers=self.headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            print(f" Targeting rules updated for '{config_key}'")
            return response.json()
        else:
            print(f" Failed to update targeting: {response.text}")
            return None

def main():
    load_dotenv()
    
    print(" LaunchDarkly AI Config Bootstrap")
    print("=" * 50)
    print("  IMPORTANT: This script is for INITIAL SETUP ONLY")
    print(" After bootstrap completes:")
    print("   • Make ALL configuration changes in LaunchDarkly UI")
    print("   • Do NOT modify ai_config_manifest.yaml")
    print("   • LaunchDarkly is your single source of truth")
    print("=" * 50)
    print()
    
    api_key = os.getenv("LD_API_KEY")
    if not api_key:
        print(" LD_API_KEY environment variable not set")
        print("   Get your API key from: https://app.launchdarkly.com/settings/authorization")
        return
    
    # Load manifest
    manifest_path = Path("ai_config_manifest_TEMP.yaml")
    if not manifest_path.exists():
        print(" ai_config_manifest_TEMP.yaml not found")
        print("   Make sure you're running this from the bootstrap/ directory")
        return
    
    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)
    
    project_key = manifest["project"]["key"]
    bootstrap = MultiAgentBootstrap(api_key)
    
    print(" Starting multi-agent system bootstrap (add-only)...")
    print(f"📦 Project: {project_key}")
    print()
    print("📋 Creation order: tools → ai configs → variations → segments → targeting")
    print()

    # 1) Tools
    if "tool" in manifest["project"]:
        print(" Creating tools...")
        part1_tool_keys = {"search_v2", "reranking"}
        for tool in manifest["project"]["tool"]:
            if tool.get("key") in part1_tool_keys:
                continue
            bootstrap.create_tool(project_key, tool)
        print()

    # 2) AI Configs (ensure they exist from Part 1)
    print("🤖 Ensuring AI configs exist...")
    existing_config_keys = set()
    for ai_config in manifest["project"]["ai_config"]:
        if bootstrap.ensure_ai_config_exists(project_key, ai_config):
            existing_config_keys.add(ai_config["key"])
    if not existing_config_keys:
        print("  No existing AI configs found. This script assumes Part 1 created base configs. Skipping variations/targeting.")
    print()

    # 3) Variations (add-only; skip if exists)
    print("🧩 Creating variations...")
    skip_variations = {"supervisor-basic"}  # Created in Part 1
    for ai_config in manifest["project"]["ai_config"]:
        config_key = ai_config["key"]
        if config_key not in existing_config_keys:
            continue
        for variation in ai_config.get("variations", []):
            if variation.get("key") in skip_variations:
                continue
            bootstrap.create_variation(project_key, config_key, variation)
    print()

    # 4) Segments (required for targeting rules)
    if "segment" in manifest["project"]:
        print("📦 Creating segments (for targeting rules)...")
        for segment in manifest["project"]["segment"]:
            bootstrap.create_segment(project_key, segment)
        print()

    # 5) Targeting (idempotent updates; skip duplicate rules)
    print(" Updating targeting rules...")
    for ai_config in manifest["project"]["ai_config"]:
        config_key = ai_config["key"]
        if config_key not in existing_config_keys:
            continue
        if "targeting" in ai_config and ai_config["targeting"].get("rules"):
            bootstrap.update_targeting(project_key, config_key, ai_config["targeting"])
        elif "targeting" in ai_config and not ai_config["targeting"].get("rules"):
            print(f"  ⏭️  Skipping targeting for '{config_key}' (empty rules)")
    print()

    print("✨ Bootstrap complete!")
    print()
    print(" Next steps:")
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