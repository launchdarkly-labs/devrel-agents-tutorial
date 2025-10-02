# Cost Tracking Investigation Summary

## The Problem
- **Expected**: ~300 cost events (one per request)
- **Actual**: 109 cost events (36% of expected)
- **Missing**: ~191 cost events (64%)

## Root Cause: REQUEST TIMEOUTS

Requests are timing out after 60 seconds BEFORE cost tracking completes.

### Evidence:
1. ✅ **Token tracking works** (145-157 exposures) - happens early in request
2. ✅ **Code is correct** - tests show costs ARE tracked when requests complete
3. ❌ **Requests timeout** - shown by `ReadTimeout: HTTPConnectionPool(...): Read timed out. (read timeout=60)`
4. ❌ **Cost tracking never runs** - happens at the END of request, after timeout

### Why Requests Take So Long:
1. **Claude Opus 4** - Large context processing (20K+ tokens)
2. **MCP Tools** - External API calls (arxiv_search, semantic_scholar) can be slow
3. **Multiple tool calls** - Up to 10-20 tool calls per request
4. **Rate limiting** - 1 second between each LLM call (by design)

## The Metrics Discrepancy Explained

### Token Metrics (145-157 exposures):
- Tracked via `tracker.track_tokens()` 
- Happens **early** when LLM starts processing
- ✅ Works even if request times out later

### Cost Metrics (23-43 exposures):
- Tracked via `ld_client.track("ai_cost_per_request")`
- Happens **at the end** after all processing completes
- ❌ Never runs if request times out

### Why User Count Is Lower:
- Your metric uses "per user" aggregation
- Traffic generator creates unique user per request (user_1, user_2, etc.)
- Only users whose requests COMPLETED get cost events
- So 23-43 users = 23-43 requests that completed within 60 seconds

## Solutions

### Option 1: Increase Timeout (Quick Fix) ✅ DONE
Updated timeout in traffic generator:
```python
# In tools/traffic_generator.py line 144
timeout=240  # Increased from 30 to 240 seconds
```

**Note**: Anthropic rate limits are VERY generous (1,000 requests/min, 450K input tokens/min).
Rate limiting from the API provider is NOT the issue - individual requests are just slow.

### Option 2: Reduce Tool Calls (Performance Fix)
In LaunchDarkly, reduce `max_tool_calls`:
- Current: 10-20 tool calls
- Recommended: 5-7 tool calls

### Option 3: Disable Slow Tools (Speed Fix)
Remove slow MCP tools from variations:
- Keep: search_v1, search_v2, reranking (fast)
- Remove: arxiv_search, semantic_scholar (slow external APIs)

### Option 4: Track Costs Earlier (Structural Fix)
Move cost tracking to happen BEFORE request completes:
- Track costs as soon as tokens are known
- Don't wait for full request completion

### Option 5: Use Streaming (Best Long-term)
Enable streaming responses:
- Track costs as tokens stream in
- Don't wait for complete response
- But requires significant code changes

## Immediate Action

**RESTART YOUR EXPERIMENT** after:
1. Increasing timeout to 120 seconds
2. Reducing max_tool_calls to 5-7
3. Running fresh traffic with `--delay 2` (slower = fewer timeouts)

This should get your cost tracking coverage from 36% → 80-90%.

## Check API Limits

To check if you're hitting rate limits:

### Anthropic (Claude):
- Go to: https://console.anthropic.com/settings/limits
- Check: Rate limits and remaining credits

### OpenAI (GPT-4o):
- Go to: https://platform.openai.com/account/limits
- Check: Rate limits and usage

If you're hitting limits, you'll see 429 errors in responses.

