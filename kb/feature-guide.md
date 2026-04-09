# Umbra Feature Guide

## Platform Overview

Umbra is a cloud platform for deploying web applications. Push to Git, we handle the rest: builds, deployments, SSL, CDN, and scaling.

## Core Features

### Git-Based Deployments

Every push to your repository triggers a deployment:

- **Production**: Pushes to `main` or `master`
- **Preview**: Pushes to any other branch
- **Instant rollback**: Click any previous deployment to restore

Supported providers: GitHub, GitLab, Bitbucket

### Framework Detection

Umbra automatically detects your framework and configures builds:

| Framework | Build Command | Output Dir |
|-----------|---------------|------------|
| Next.js | `next build` | `.next` |
| Remix | `remix build` | `build` |
| Astro | `astro build` | `dist` |
| SvelteKit | `vite build` | `build` |
| Nuxt | `nuxt build` | `.output` |

Override in `umbra.toml` if needed.

### Serverless Functions

Write backend logic that scales automatically:

```typescript
// api/hello.ts
export default function handler(req, res) {
  res.json({ message: 'Hello from Umbra' });
}
```

- Automatic routing: `/api/hello`
- Cold start: <100ms
- Timeout: 10s (Hobby), 60s (Pro), 300s (Enterprise)

### Edge Functions

Run code at the edge, closest to your users:

```typescript
// middleware.ts
export function middleware(request) {
  // Runs before every request
  return NextResponse.next();
}
```

- <1ms overhead
- Available in all 80+ edge locations
- Ideal for auth, redirects, A/B testing

### Environment Variables

Manage secrets securely:

- Encrypted at rest
- Available during build and runtime
- Per-environment (Production, Preview, Development)
- Sensitive values redacted in logs

### Custom Domains

- Free SSL certificates (auto-renewed)
- Automatic HTTPS redirect
- Subdomain support
- Wildcard domains (Team+)

## Analytics

### Web Analytics (Pro+)

Privacy-friendly analytics built in:

- Page views and unique visitors
- Top pages and referrers
- Country and device breakdown
- No cookies, GDPR compliant

### Speed Insights (Pro+)

Real user performance metrics:

- Core Web Vitals (LCP, FID, CLS)
- Time to First Byte
- Per-page breakdown
- Historical trends

## CLI

Install the Umbra CLI:

```bash
npm i -g umbra
```

Commands:
- `umbra login` - Authenticate
- `umbra deploy` - Deploy current directory
- `umbra env pull` - Download env vars to `.env.local`
- `umbra logs` - Tail production logs
- `umbra dev` - Local development with Umbra runtime

## Integrations

### Databases

One-click integrations:
- Postgres (Neon, Supabase, PlanetScale)
- Redis (Upstash)
- MongoDB Atlas

### Storage

- Umbra Blob Storage (built-in)
- AWS S3
- Cloudflare R2

### Monitoring

- Datadog
- Sentry
- LogRocket

## Build Configuration

### umbra.toml

```toml
[build]
command = "npm run build"
output = "dist"

[functions]
memory = 1024  # MB
timeout = 30   # seconds

[regions]
primary = "us-east-1"

[headers]
"/api/*" = { "Cache-Control" = "no-store" }
```

### Build Environment

- Node.js: 18, 20 (default), 22
- pnpm, npm, yarn, bun supported
- 8 GB RAM, 4 vCPUs

## Limits by Plan

| Feature | Hobby | Pro | Team | Enterprise |
|---------|-------|-----|------|------------|
| Bandwidth | 100 GB | 1 TB | 5 TB | Custom |
| Functions | 100K/mo | 1M/mo | 10M/mo | Custom |
| Build minutes | 100/mo | 1,000/mo | 5,000/mo | Custom |
| Concurrent builds | 1 | 3 | 10 | Custom |
| Team members | 1 | 1 | Unlimited | Unlimited |
| Preview deployments | 10 | 100 | Unlimited | Unlimited |
| Function timeout | 10s | 60s | 60s | 300s |
| Log retention | 1 day | 7 days | 30 days | 1 year |

## Free Trial

**14-day free trial of Pro features. No credit card required.**

What you get:
- 1 TB bandwidth
- 1M function invocations
- All Pro features

After trial:
- Subscribe to Pro ($20/mo) to keep features
- Or continue on Hobby with reduced limits
- No action needed to downgrade - happens automatically
