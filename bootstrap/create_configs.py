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

    def create_project(self, project_key, project_name=None):
        """Create a LaunchDarkly project if it doesn't exist"""
        url = f"{self.base_url}/api/v2/projects"

        # Check if project exists
        check_url = f"{self.base_url}/api/v2/projects/{project_key}"
        check_response = requests.get(check_url, headers=self.headers, timeout=30)

        if check_response.status_code == 200:
            print(f"  ✅ Project '{project_key}' exists")
            # Extract SDK keys
            project_data = check_response.json()
            environments = project_data.get("environments", {})
            if "items" in environments:
                for env in environments["items"]:
                    if env.get("key") == "production":
                        sdk_key = env.get("apiKey")
                        if sdk_key:
                            print(f"     SDK Key (production): {sdk_key}")
            return True

        # Create project
        name = project_name or project_key.replace("-", " ").title()
        payload = {
            "key": project_key,
            "name": name
        }

        response = requests.post(url, headers=self.headers, json=payload, timeout=30)

        if response.status_code in [200, 201]:
            print(f"  ✅ Project '{project_key}' created")
            # Extract SDK keys from response
            project_data = response.json()
            environments = project_data.get("environments", {})
            if "items" in environments:
                for env in environments["items"]:
                    env_key = env.get("key")
                    sdk_key = env.get("apiKey")
                    if sdk_key:
                        print(f"     SDK Key ({env_key}): {sdk_key}")
            time.sleep(1)  # Wait for project to be ready
            return True
        else:
            print(f"  ❌ Failed to create project: {response.text}")
            return False

    def create_segment(self, project_key, segment_data):
        """Create user segment for targeting using two-step process"""
        url = f"{self.base_url}/api/v2/segments/{project_key}/production"
        
        # Step 1: Create empty segment (LaunchDarkly ignores rules in POST)
        payload = {
            "key": segment_data["key"],
            "name": segment_data["key"].replace("-", " ").title()
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
        
        # Use modelId directly as modelConfigKey (format: Provider.model-name)
        model_config = variation_data["modelConfig"]
        model_config_key = model_config["modelId"]
        
        payload = {
            "key": variation_data["key"],
            "name": variation_data.get("name", variation_data["key"].replace("-", " ").title()),
            "messages": [],  # Empty array required for agent mode validation
            "instructions": variation_data["instructions"],
            "tools": [{"key": tool, "version": 1} for tool in variation_data.get("tools", [])]
        }
        
        payload["modelConfigKey"] = model_config_key
        print(f"   Using modelConfigKey: {model_config_key}")
        
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
        
        # Use modelId directly as modelConfigKey
        model_config_key = variation_data["modelConfig"]["modelId"]

        payload = {
            "instructions": variation_data["instructions"],
            "tools": [{"key": tool, "version": 1} for tool in variation_data.get("tools", [])],
            "modelConfigKey": model_config_key
        }
        print(f"     Updating with modelConfigKey: {model_config_key}")
        
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
        """Ensure an AI Config exists; create it if it doesn't."""
        config_key = config_data["key"]
        config_name = config_data.get("name", config_key.replace("-", " ").title())
        url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs/{config_key}"
        response = requests.get(url, headers=self.headers, timeout=30)
        if response.status_code == 200:
            print(f"  ✅ AI Config '{config_key}' exists")
            return True
        else:
            # Create the AI Config
            print(f"  📝 Creating AI Config '{config_key}'...")
            create_url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs"
            payload = {
                "key": config_key,
                "name": config_name,
                "mode": "agent"
            }
            create_response = requests.post(create_url, headers=self.headers, json=payload, timeout=30)
            if create_response.status_code in [200, 201]:
                print(f"  ✅ AI Config '{config_key}' created")
                time.sleep(0.5)
                return True
            else:
                print(f"  ❌ Failed to create AI Config '{config_key}': {create_response.text}")
                return False

    # Removed detachment logic per new overwrite deletion order requirements

    def enable_ai_config(self, project_key, config_key, default_variation_key=None):
        """Verify an AI Config is enabled and optionally set the default variation"""
        url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs/{config_key}/targeting"

        # First get targeting to check status and find variation IDs
        response = requests.get(url, headers=self.headers, timeout=30)
        if response.status_code != 200:
            print(f"  ❌ Could not get targeting for '{config_key}': {response.text}")
            return False

        targeting_data = response.json()
        variations = targeting_data.get("variations", [])

        # Check if already enabled in production
        environments = targeting_data.get("environments", {})
        production_env = environments.get("production", {})
        is_enabled = production_env.get("enabled", False)

        if is_enabled:
            print(f"  ✅ AI Config '{config_key}' is already enabled")
        else:
            # Enable targeting
            enable_instructions = [{
                "kind": "turnTargetingOn"
            }]
            enable_payload = {
                "environmentKey": "production",
                "instructions": enable_instructions
            }
            enable_response = requests.patch(url, headers=self.headers, json=enable_payload, timeout=30)
            if enable_response.status_code == 200:
                print(f"  ✅ AI Config '{config_key}' targeting enabled")
            else:
                print(f"  ❌ Failed to enable targeting for '{config_key}': {enable_response.text}")

        # Set default variation if specified and not already set
        if default_variation_key:
            variation_id = None
            for var in variations:
                # Skip the "disabled" variation
                if var.get("name") == "disabled":
                    continue
                # Check the variation key from _ldMeta
                var_value = var.get("value", {})
                ld_meta = var_value.get("_ldMeta", {})
                var_key = ld_meta.get("variationKey")
                if var_key == default_variation_key:
                    variation_id = var["_id"]
                    break

            if variation_id:
                instructions = [{
                    "kind": "updateFallthroughVariationOrRollout",
                    "variationId": variation_id
                }]

                payload = {
                    "environmentKey": "production",
                    "instructions": instructions
                }

                patch_response = requests.patch(url, headers=self.headers, json=payload, timeout=30)

                if patch_response.status_code == 200:
                    print(f"    → Default variation set to '{default_variation_key}'")
                # Silently ignore if already set (duplicate error)

        return is_enabled

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
    manifest_path = Path("ai_config_manifest.yaml")
    if not manifest_path.exists():
        print(" ai_config_manifest.yaml not found")
        print("   Make sure you're running this from the bootstrap/ directory")
        return
    
    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)
    
    project_key = manifest["project"]["key"]
    bootstrap = MultiAgentBootstrap(api_key)

    print("🚀 Starting multi-agent system bootstrap...")
    print(f"📦 Project: {project_key}")
    print()
    print("📋 Creation order: project → tools → ai configs → variations → segments → targeting → enable")
    print()

    # 0) Create project if it doesn't exist
    print("📁 Ensuring project exists...")
    if not bootstrap.create_project(project_key, manifest["project"].get("name")):
        print("  ❌ Failed to create or verify project. Exiting.")
        return
    print()

    # 1) Tools
    if "tool" in manifest["project"]:
        print("🔧 Creating tools...")
        for tool in manifest["project"]["tool"]:
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
    for ai_config in manifest["project"]["ai_config"]:
        config_key = ai_config["key"]
        if config_key not in existing_config_keys:
            continue
        for variation in ai_config.get("variations", []):
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

    # 6) Enable AI Configs (turn them on so they serve in production)
    print("🚀 Enabling AI Configs...")
    for ai_config in manifest["project"]["ai_config"]:
        config_key = ai_config["key"]
        if config_key not in existing_config_keys:
            continue
        # Use the defaultVariation from targeting config
        default_variation = None
        if "targeting" in ai_config:
            default_variation = ai_config["targeting"].get("defaultVariation")
        bootstrap.enable_ai_config(project_key, config_key, default_variation)
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