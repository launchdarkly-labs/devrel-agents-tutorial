# Umbra Troubleshooting Guide

## Build Failures

### "Module not found" errors

Your dependencies aren't installing correctly.

1. Check `package.json` - is the module listed?
2. Delete `node_modules` and lockfile, reinstall locally
3. Ensure you're not using a local-only path alias

```bash
# Clear Umbra's build cache
umbra deploy --force
```

### "Out of memory" during build

Your build exceeds the 8 GB limit.

Solutions:
- Add `NODE_OPTIONS=--max_old_space_size=7168` to env vars
- Split large bundles
- Reduce concurrent compilation (disable parallel TypeScript)

### Build timeout

Builds must complete within 45 minutes.

Solutions:
- Cache dependencies (automatic for npm/yarn/pnpm)
- Reduce bundle size
- Skip unnecessary build steps in CI

### Framework not detected

Umbra didn't recognize your framework.

Add explicit configuration:

```toml
# umbra.toml
[build]
command = "npm run build"
output = "dist"
```

## Deployment Issues

### "Function timeout" errors

Your serverless function exceeded its limit:
- Hobby: 10 seconds
- Pro/Team: 60 seconds
- Enterprise: 300 seconds

Solutions:
- Optimize slow database queries
- Add connection pooling
- Use background jobs for long tasks
- Upgrade plan for higher limits

### "Cold start" latency

First request after idle period is slow.

Mitigations:
- Keep functions small (<50MB)
- Minimize dependencies
- Use edge functions for latency-critical paths
- Enterprise: Provisioned concurrency

### "502 Bad Gateway"

Your function crashed or didn't respond.

Check:
1. Function logs: `umbra logs --function api/yourfunction`
2. Is there an unhandled exception?
3. Does the function return a response?
4. Memory limit exceeded? (Check for "SIGKILL")

### Domain not resolving

DNS hasn't propagated yet.

Steps:
1. Verify DNS records in your domain provider match Umbra's instructions
2. Wait 24-48 hours for propagation
3. Check: `dig yourdomain.com`
4. SSL issues? Try: Settings → Domains → Refresh Certificate

## Account Issues

### Can't log in

Authentication is through your Git provider.

Steps:
1. Try logging in directly to GitHub/GitLab/Bitbucket
2. Clear browser cookies
3. Revoke and re-authorize Umbra in your Git provider settings
4. Contact support if still stuck

### Payment failed

**We retry failed payments 3 times over 9 days. After that, your account is downgraded to Hobby tier.**

Common causes:
- Expired card
- Insufficient funds
- Bank blocked the charge (new vendor)

Fix: Settings → Billing → Update Payment Method

### Team member can't access project

Check their role:
- Viewer: Can see deployments, can't change anything
- Developer: Can deploy and manage projects
- Admin: Full access including billing

Update roles: Team Settings → Members

### Hit usage limits

If you exceed plan limits:
- Bandwidth: Deployments stay live, but may throttle
- Functions: Additional invocations return 429 errors
- Build minutes: Builds queue until next billing period

Check usage: Settings → Usage

Upgrade plan or wait for monthly reset.

## Performance Issues

### Slow page loads

1. Check Speed Insights: Are Core Web Vitals failing?
2. Large JavaScript bundle? Enable code splitting
3. Images not optimized? Use next/image or similar
4. No caching? Add Cache-Control headers

### High function latency

1. Check logs for slow operations
2. Database far from function region? Use connection pooling
3. Too many dependencies? Cold starts will be slow
4. Consider edge functions for simple logic

### Intermittent failures

1. Check status.umbra.dev for incidents
2. Review logs for patterns (specific times, routes, users)
3. Rate limiting? Check if hitting API limits
4. Regional issues? Check deployment regions

## CLI Issues

### "Authentication failed"

```bash
umbra logout
umbra login
```

If still failing, delete `~/.umbra/credentials.json` and re-login.

### "Project not found"

You're not in a linked directory, or project was deleted.

```bash
# Link to existing project
umbra link

# Or create new project
umbra init
```

### Commands hang

Check your network connection. Umbra CLI requires HTTPS access to api.umbra.dev.

If behind a proxy:
```bash
export HTTPS_PROXY=http://your-proxy:8080
```

## Getting Help

### Self-Service

- Docs: docs.umbra.dev
- Status: status.umbra.dev
- Community: community.umbra.dev

### Support Channels

| Plan | Channel | Response Time |
|------|---------|---------------|
| Hobby | Community forum | Best effort |
| Pro | Email | 24 hours |
| Team | Email + Chat | 4 hours |
| Enterprise | Dedicated Slack | 1 hour |

Contact support: umbra.dev/support

### What to Include in Support Requests

1. Team slug and project name
2. Deployment URL or ID
3. Timestamps of the issue
4. Error messages (exact text or screenshots)
5. Steps to reproduce

## Common Error Messages

### "Rate limited (429)"

You've exceeded API or function invocation limits. Wait 60 seconds and retry, or upgrade your plan.

### "Payload too large (413)"

Request body exceeds 4.5 MB limit. For file uploads, use Umbra Blob Storage or direct-to-S3 uploads.

### "Unauthorized (401)"

Your access token is invalid or expired. Generate a new token in Settings → Tokens.

### "Region unavailable"

The specified region is experiencing issues. Check status.umbra.dev or deploy to a different region.
