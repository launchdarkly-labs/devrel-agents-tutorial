#!/usr/bin/env python3
"""
List all environments in the LaunchDarkly project
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

def list_environments():
    """List all environments in the project"""
    api_key = os.getenv('LD_API_KEY')
    project_key = "default"  # Your project key
    
    if not api_key:
        print("❌ ERROR: LD_API_KEY not found in .env file")
        return
    
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }
    
    print(f"🔍 Fetching environments for project '{project_key}'...\n")
    response = requests.get(
        f"https://app.launchdarkly.com/api/v2/projects/{project_key}",
        headers=headers,
        timeout=10
    )
    
    if response.status_code == 200:
        data = response.json()
        environments = data.get('environments', {}).get('items', [])
        
        print(f"Found {len(environments)} environment(s):\n")
        print("=" * 60)
        
        for env in environments:
            print(f"  Key:  {env['key']}")
            print(f"  Name: {env['name']}")
            print("-" * 60)
        
        if environments:
            print("\n💡 The bootstrap script needs to use one of these environment keys.")
            print(f"   Currently hardcoded to: 'production'")
            print(f"   Your actual environments: {[e['key'] for e in environments]}")
        else:
            print("\n⚠️  No environments found in this project!")
        
    else:
        print(f"❌ Failed to fetch project: {response.status_code}")
        print(f"   Response: {response.text}")

if __name__ == "__main__":
    list_environments()
