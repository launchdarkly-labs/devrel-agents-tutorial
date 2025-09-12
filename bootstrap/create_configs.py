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
        """Create AI Config with variations"""
        url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs"
        
        payload = {
            "key": config_data["key"],
            "name": config_data["name"],
            "configType": "agent"
        }
        
        response = requests.post(url, headers=self.headers, json=payload, timeout=30)
        
        if response.status_code in [200, 201]:
            print(f"✅ AI Config '{config_data['key']}' created")
            time.sleep(0.5)
            
            # Create variations
            for variation in config_data["variations"]:
                self.create_variation(project_key, config_data["key"], variation)
            
            # Set up targeting
            self.update_targeting(project_key, config_data["key"], config_data["targeting"])
            
            return response.json()
        elif response.status_code == 409:
            print(f"⚠️  AI Config '{config_data['key']}' already exists")
            return None
        else:
            print(f"❌ Failed to create AI Config: {response.status_code} - {response.text}")
            return None
    
    def create_variation(self, project_key, config_key, variation_data):
        """Create AI Config variation"""
        url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs/{config_key}/variations"
        
        payload = {
            "key": variation_data["key"],
            "modelConfig": variation_data["modelConfig"],
            "prompt": {
                "messages": [
                    {
                        "role": "system",
                        "content": variation_data["instructions"]
                    }
                ]
            },
            "tools": [{"key": tool} for tool in variation_data.get("tools", [])],
            "customParameters": variation_data.get("customParameters", {})
        }
        
        response = requests.post(url, headers=self.headers, json=payload, timeout=30)
        
        if response.status_code in [200, 201]:
            print(f"  ✅ Variation '{variation_data['key']}' created")
            time.sleep(0.5)
            return response.json()
        else:
            print(f"  ❌ Failed to create variation: {response.status_code} - {response.text}")
            return None
    
    def update_targeting(self, project_key, config_key, targeting_data):
        """Update AI Config targeting rules"""
        url = f"{self.base_url}/api/v2/projects/{project_key}/ai-configs/{config_key}/environments/production/targeting"
        
        rules = []
        for rule in targeting_data["rules"]:
            rule_config = {
                "clauses": [
                    {
                        "attribute": "segmentMatch",
                        "op": "segmentMatch",
                        "values": rule["segments"],
                        "contextKind": "user"
                    }
                ],
                "variationId": rule["variation"]  # Will be resolved to actual ID
            }
            rules.append(rule_config)
        
        payload = {
            "rules": rules,
            "fallthrough": {
                "variationId": targeting_data["defaultVariation"]
            },
            "on": True
        }
        
        response = requests.patch(url, headers=self.headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            print(f"✅ Targeting rules updated for '{config_key}'")
            return response.json()
        else:
            print(f"❌ Failed to update targeting: {response.status_code} - {response.text}")
            return None

def main():
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
    
    print("🚀 Starting multi-agent system bootstrap...")
    print(f"📦 Project: {project_key}")
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