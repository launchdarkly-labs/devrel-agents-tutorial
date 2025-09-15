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
        """Create user segment for targeting"""
        url = f"{self.base_url}/api/v2/segments/{project_key}/production"
        
        payload = {
            "key": segment_data["key"],
            "name": segment_data["key"].replace("-", " ").title(),
            "rules": segment_data["rules"]
        }
        
        response = requests.post(url, headers=self.headers, json=payload, timeout=30)
        
        if response.status_code in [200, 201]:
            print(f"✅ Segment '{segment_data['key']}' created")
            time.sleep(0.5)
            return response.json()
        elif response.status_code == 409:
            print(f"⚠️  Segment '{segment_data['key']}' already exists")
            return None
        else:
            print(f"❌ Failed to create segment: {response.status_code} - {response.text}")
            return None
    
    def create_ai_config(self, project_key, config_data):
        """Add variations to existing AI Config or create if not exists"""
        # Check if config already exists
        check_url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs/{config_data['key']}"
        check_response = requests.get(check_url, headers=self.headers, timeout=30)
        
        if check_response.status_code == 200:
            print(f"✅ AI Config '{config_data['key']}' exists, adding variations")
            config_exists = True
        else:
            print(f"⚠️  AI Config '{config_data['key']}' not found, skipping creation")
            return None
        
        # Add variations to existing config
        for variation in config_data["variations"]:
            self.create_variation(project_key, config_data["key"], variation)
        
        # Set up targeting
        if "targeting" in config_data:
            self.update_targeting(project_key, config_data["key"], config_data["targeting"])
        
        return {"key": config_data["key"], "status": "updated"}
    
    def create_variation(self, project_key, config_key, variation_data):
        """Create AI Config variation"""
        url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs/{config_key}/variations"
        
        # Build model structure to match existing format
        model_config = variation_data["modelConfig"]
        model = {
            "modelName": model_config["modelId"],
            "custom": variation_data.get("customParameters", {}),
            "parameters": {}
        }
        
        payload = {
            "key": variation_data["key"],
            "name": variation_data.get("name", variation_data["key"].replace("-", " ").title()),
            "messages": [],  # Empty array required for agent mode validation
            "instructions": variation_data["instructions"],
            "modelName": model_config["modelId"],
            "provider": {"name": model_config["provider"].title()},
            "tools": [{"key": tool, "version": 1} for tool in variation_data.get("tools", [])]
        }
        
        print(f"DEBUG: Sending payload: {json.dumps(payload, indent=2)}")
        response = requests.post(url, headers=self.headers, json=payload, timeout=30)
        
        if response.status_code in [200, 201]:
            print(f"  ✅ Variation '{variation_data['key']}' created")
            time.sleep(0.5)
            return response.json()
        elif response.status_code == 409:
            if self.overwrite:
                print(f"  🔄 Variation '{variation_data['key']}' exists, updating...")
                return self.update_variation(project_key, config_key, variation_data)
            else:
                print(f"  ⚠️  Variation '{variation_data['key']}' already exists (use --overwrite to update)")
                return None
        else:
            print(f"  ❌ Failed to create variation: {response.status_code} - {response.text}")
            return None
    
    def update_variation(self, project_key, config_key, variation_data):
        """Update existing AI Config variation"""
        # First get the existing variation ID
        config_url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs/{config_key}"
        config_response = requests.get(config_url, headers=self.headers, timeout=30)
        
        if config_response.status_code != 200:
            print(f"    ❌ Could not fetch config to get variation ID")
            return None
            
        config_data = config_response.json()
        variations = config_data.get("variations", [])
        variation_id = None
        
        for variation in variations:
            if variation["key"] == variation_data["key"]:
                variation_id = variation["_id"]
                break
                
        if not variation_id:
            print(f"    ❌ Could not find variation ID for '{variation_data['key']}'")
            return None
        
        # Update the variation using PATCH
        url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs/{config_key}/variations/{variation_id}"
        
        # Build the same payload as create
        model_config = variation_data["modelConfig"]
        
        payload = {
            "instructions": variation_data["instructions"],
            "modelName": model_config["modelId"],
            "provider": {"name": model_config["provider"].title()},
            "tools": [{"key": tool, "version": 1} for tool in variation_data.get("tools", [])]
        }
        
        response = requests.patch(url, headers=self.headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            print(f"    ✅ Variation '{variation_data['key']}' updated")
            time.sleep(0.5)
            return response.json()
        else:
            print(f"    ❌ Failed to update variation: {response.status_code} - {response.text}")
            return None
    
    def create_tool(self, project_key, tool_data):
        """Create tool for AI Configs"""
        url = f"{self.base_url}/api/v2/projects/{project_key}/tools"
        
        payload = {
            "key": tool_data["key"],
            "name": tool_data["name"],
            "description": tool_data["description"],
            "type": tool_data.get("type", "function")
        }
        
        # Add MCP-specific configuration if applicable
        if tool_data.get("type") == "mcp":
            payload["mcpServer"] = tool_data.get("server", "")
        
        response = requests.post(url, headers=self.headers, json=payload, timeout=30)
        
        if response.status_code in [200, 201]:
            print(f"✅ Tool '{tool_data['key']}' created")
            time.sleep(0.5)
            return response.json()
        elif response.status_code == 409:
            print(f"⚠️  Tool '{tool_data['key']}' already exists")
            return None
        else:
            print(f"❌ Failed to create tool: {response.status_code} - {response.text}")
            return None

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
            print(f"❌ Failed to fetch targeting data: {response.status_code} - {response.text}")
            return {}

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
        
        response = requests.patch(url, headers=self.headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            print(f"✅ Targeting rules updated for '{config_key}'")
            return response.json()
        else:
            print(f"❌ Failed to update targeting: {response.status_code} - {response.text}")
            return None

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Bootstrap LaunchDarkly AI Configs")
    parser.add_argument("--overwrite", action="store_true", 
                       help="Update existing variations instead of skipping them")
    args = parser.parse_args()
    
    load_dotenv()
    
    api_key = os.getenv("LD_API_KEY")
    if not api_key:
        print("❌ LD_API_KEY environment variable not set")
        print("   Get your API key from: https://app.launchdarkly.com/settings/authorization")
        return
    
    # Load manifest
    manifest_path = Path("ai_config_manifest.yaml")
    if not manifest_path.exists():
        print("❌ ai_config_manifest.yaml not found")
        print("   Make sure you're running this from the bootstrap/ directory")
        return
    
    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)
    
    project_key = manifest["project"]["key"]
    bootstrap = MultiAgentBootstrap(api_key)
    bootstrap.overwrite = args.overwrite
    
    print("🚀 Starting multi-agent system bootstrap...")
    print(f"📦 Project: {project_key}")
    if args.overwrite:
        print("🔄 Overwrite mode: Will update existing variations")
    print()
    
    # Create segments
    print("📦 Creating segments...")
    for segment in manifest["project"]["segment"]:
        bootstrap.create_segment(project_key, segment)
    print()
    
    # Create AI configs
    print("🤖 Creating AI configs...")
    for ai_config in manifest["project"]["ai_config"]:
        bootstrap.create_ai_config(project_key, ai_config)
    print()
    
    print("✨ Bootstrap complete!")
    print()
    print("🎯 Next steps:")
    print("   1. Check your LaunchDarkly dashboard to verify configurations")
    print("   2. Test different user contexts with the demo")
    print("   3. Monitor usage patterns and adjust targeting rules")

if __name__ == "__main__":
    main()