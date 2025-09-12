# LaunchDarkly Multi-Agent Bootstrap

Automated setup for advanced multi-agent configurations with geographic targeting, business tiers, and cost optimization.

## Quick Start

### 1. Set Environment Variables
```bash
export LD_API_KEY="your-launchdarkly-api-key"
```

Get your API key from: [LaunchDarkly API Keys](https://app.launchdarkly.com/settings/authorization)

### 2. Install Dependencies
```bash
cd bootstrap
pip install -r requirements.txt
```

### 3. Update Configuration
Edit `ai_config_manifest.yaml` and update the project key:
```yaml
project:
  key: "your-project-key"  # Change this to your LaunchDarkly project
```

### 4. Run Bootstrap
```bash
python create_configs.py
```

## What Gets Created

### Segments
- **Geographic**: `eu-users`, `us-users` 
- **Business Tiers**: `enterprise-users`, `pro-users`, `free-users`
- **Combined**: `eu-enterprise`, `us-enterprise`

### AI Config
- **Key**: `support-agent-business-tiers`
- **6 Variations**: EU/US × Free/Pro/Enterprise matrix
- **Targeting Rules**: Automatic user routing based on geography and plan

### Targeting Matrix
```
            │  Free      │  Pro         │  Enterprise
────────────┼────────────┼──────────────┼────────────────
EU Users    │  Claude H  │  Claude H    │  Claude S + MCP
            │  Basic RAG │  Full RAG    │  Full Tools
US Users    │  GPT Mini  │  GPT-4       │  GPT-4 + MCP  
            │  Basic RAG │  Full RAG    │  Full Tools
```

## Configuration Details

### Cost Limits by Tier
- **Free**: $0.10 per session, 3 tool calls
- **Pro**: $1.00 per session, 8 tool calls  
- **Enterprise**: $10.00 per session, 20 tool calls

### Privacy Protection
- **EU Users**: Always routed to Claude models for enhanced privacy
- **US Users**: Cost-optimized with OpenAI models
- **PII Detection**: Automatic redaction through security agent

### Tool Access
- **Basic**: Internal RAG search only
- **Enhanced**: RAG + ArXiv research
- **Premium**: Full MCP tool suite (ArXiv, Semantic Scholar)

## Customization

### Adding New Segments
```yaml
segment:
  - key: asia-pacific-users
    rules:
    - attribute: "country"
      op: "in"
      values: ["JP", "AU", "SG", "HK"]
      contextKind: "user"
```

### Modifying Cost Limits
```yaml
customParameters:
  max_cost_per_session: 5.00  # Increase limit
  max_tool_calls: 15          # More tool calls
```

### Adding Variations
```yaml
- key: "custom-variation"
  modelConfig:
    provider: "anthropic"
    modelId: "claude-3-5-sonnet-20241022"
  tools: ["search_v1", "custom_tool"]
  instructions: "Custom agent behavior"
```

## Troubleshooting

### Common Issues

**API Key Error**
```
❌ LD_API_KEY environment variable not set
```
Solution: Set your LaunchDarkly API key as environment variable

**Project Not Found**
```
❌ Failed to create AI Config: 404
```
Solution: Update the project key in `ai_config_manifest.yaml`

**Permission Denied**
```
❌ Failed to create segment: 403
```
Solution: Ensure your API key has Admin or Writer permissions

### Re-running the Script

The bootstrap script is idempotent:
- **Existing segments**: Skipped with warning
- **Existing AI configs**: Skipped with warning
- **Targeting rules**: Updated with new configuration

## Next Steps

1. **Verify Setup**: Check LaunchDarkly dashboard for created configurations
2. **Test Targeting**: Use different user contexts to verify routing
3. **Monitor Usage**: Track costs and performance across tiers
4. **Iterate**: Adjust targeting rules based on user behavior

## Files Overview

- `ai_config_manifest.yaml`: Complete configuration definition
- `create_configs.py`: Bootstrap script with LaunchDarkly API integration
- `requirements.txt`: Python dependencies
- `README.md`: This documentation