# Umbra Deployment Regions

## Overview

Umbra deploys your applications to edge locations worldwide. This document covers our region availability, latency characteristics, and data residency options.

## Available Regions

### Primary Regions (Full Feature Support)

| Region | Location | Latency to Users |
|--------|----------|------------------|
| `us-east-1` | Virginia, USA | <20ms North America East |
| `us-west-2` | Oregon, USA | <20ms North America West |
| `eu-west-1` | Dublin, Ireland | <20ms Western Europe |
| `eu-central-1` | Frankfurt, Germany | <20ms Central Europe |
| `ap-northeast-1` | Tokyo, Japan | <20ms East Asia |
| `ap-southeast-1` | Singapore | <30ms Southeast Asia |

### Edge Locations (Static Assets + Edge Functions)

We serve static assets from 80+ edge locations globally. Edge functions run in all primary regions plus:

- Sydney, Australia
- São Paulo, Brazil
- Mumbai, India
- Seoul, South Korea
- Cape Town, South Africa

### Regions We Do NOT Support

Due to regulatory requirements, we cannot deploy to:

- China (mainland) - use a local provider
- Russia
- Iran
- North Korea
- Cuba

For China deployment, we recommend partnering with a local provider and using our API to sync deployments.

## Deployment Times

| Deployment Type | Time to Global |
|-----------------|----------------|
| Static assets | 30-60 seconds |
| Serverless functions | 45-90 seconds |
| Edge functions | 60-120 seconds |
| Full redeploy | 2-3 minutes |

## Data Residency

### GDPR Compliance

For EU data residency requirements:
- Select `eu-west-1` or `eu-central-1` as your primary region
- Enable "EU-only" mode in project settings
- This restricts function execution to EU regions only

### SOC 2 and HIPAA

Available on Enterprise plans:
- Dedicated compute isolation
- Custom data retention policies
- Audit logging to your SIEM

## Region Selection

### Automatic (Recommended)

By default, Umbra routes requests to the nearest healthy region. This provides:
- Lowest latency for global users
- Automatic failover
- No configuration needed

### Manual Region Lock

For compliance or latency requirements:

```toml
# umbra.toml
[regions]
primary = "eu-west-1"
allowed = ["eu-west-1", "eu-central-1"]
```

## Migration Between Regions

Moving your deployment to a new region:

1. Update `umbra.toml` with new region configuration
2. Redeploy: `umbra deploy --force`
3. Update DNS if using custom domains
4. Cold starts may occur in new regions

No data migration is needed - your source is redeployed from your repository.
