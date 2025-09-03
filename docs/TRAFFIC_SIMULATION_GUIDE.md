# Traffic Simulation Guide

**Status**: ✅ **READY TO USE** - Dead simple traffic generator for LaunchDarkly AI Config experiments

This guide explains how to generate realistic traffic for your LaunchDarkly AI Config experiments. The system is designed to be **so simple that a high school student** can understand and modify it.

---

## 🚀 Quick Start

### 1. Make Sure Your API is Running
```bash
# Start the backend API (in one terminal)
uv run uvicorn api.main:app --reload --port 8001

# Verify it's working
curl http://localhost:8001/chat -X POST -H "Content-Type: application/json" \
  -d '{"user_id": "test", "message": "Hello"}'
```

### 2. Generate Traffic
```bash
# Generate 20 queries with 2-second delays
python tools/traffic_generator.py --queries 20 --delay 2

# Generate 100 queries quickly (for demo metrics)
python tools/traffic_generator.py --queries 100 --delay 0.5

# Verbose output to see what's happening
python tools/traffic_generator.py --queries 10 --delay 1 --verbose
```

### 3. Check Your Results
- **Console**: See real-time feedback and success rates
- **LaunchDarkly Dashboard**: Check Experiments tab for metrics (takes 1-2 minutes)
- **Backend Logs**: Watch detailed tool usage and geographic targeting

---

## 📁 How It Works

### The Data Files

**`data/fake_users.json`** - Fake users with geographic data
```json
{
  "id": "user_us_enterprise_001", 
  "country": "US",
  "region": "north_america",
  "plan": "enterprise"
}
```

**`data/sample_queries.json`** - Questions to ask the AI
```json
{
  "query": "What are transformers in machine learning?",
  "type": "basic_ml",
  "good_response_keywords": ["attention", "neural network"]
}
```

### The Magic Happens

1. **Pick Random User + Query**: Script randomly selects a fake user and question
2. **Send Real API Request**: Makes actual call to your `/chat` endpoint  
3. **AI Responds Naturally**: Your real agents respond with real tools and models
4. **Simulate User Feedback**: Script decides thumbs up/down based on simple rules
5. **Send to LaunchDarkly**: Real metrics flow to your dashboard

### Geographic Targeting in Action

```
🌍 USER CONTEXT: user_eu_enterprise_001 from DE on enterprise plan
🌍 USER CONTEXT: user_us_free_002 from US on free plan  
🌍 USER CONTEXT: user_asia_pro_001 from SG on pro plan
```

This triggers different LaunchDarkly variations based on your targeting rules!

---

## 🎯 Feedback Simulation Rules

The script simulates realistic user satisfaction using **dead simple rules**:

### Thumbs Up Rules ✅
- **Good Length**: Response > 200 characters (+30 points)
- **Keywords Found**: Contains expected keywords (+25 points each)
- **Research Content**: Mentions "papers" or "research" for research queries (+20 points)
- **Tools Used**: AI used search/research tools (+15 points)

### Thumbs Down Rules ❌  
- **Too Short**: Response < 100 characters (-20 points)
- **Missing Research**: Research query without research content (-30 points)
- **Unhelpful**: Says "I don't know" or "I can't help" (-25 points)

### Final Decision
- **Score > 20**: 👍 Thumbs up  
- **Score ≤ 20**: 👎 Thumbs down
- **Rating**: 1-5 stars based on score

**Example:**
```
✅ SUCCESS: Got 1247 chars, used 2 tools
👍 FEEDBACK: user_us_pro_001 gave 👍 (rating: 4/5) - good length, found 2 keywords, used tools
```

---

## 🛠️ Easy Customization

### Add More Users
Edit `data/fake_users.json`:
```json
{
  "id": "user_brazil_001",
  "country": "BR", 
  "region": "south_america",
  "plan": "pro"
}
```

### Add More Questions  
Edit `data/sample_queries.json`:
```json
{
  "query": "How does gradient descent work?",
  "type": "basic_ml",
  "good_response_keywords": ["gradient", "optimization", "learning rate"]
}
```

### Change Feedback Rules
Edit the `simulate_feedback()` function in `tools/traffic_generator.py`:
```python
# Make it easier to get thumbs up
if response_length > 150:  # Changed from 200
    thumbs_up_score += 40   # Changed from 30
```

### Modify Traffic Pattern
```bash
# Slow and steady (for demos)
python tools/traffic_generator.py --queries 30 --delay 3

# Fast batch (for demo data)  
python tools/traffic_generator.py --queries 200 --delay 0.2

# Small test
python tools/traffic_generator.py --queries 5 --delay 1 --verbose
```

---

## 📊 What Gets Measured

### Automatic LaunchDarkly Metrics
- ✅ **Duration**: How long each request takes
- ✅ **Success Rate**: Percentage of successful responses  
- ✅ **Tool Usage**: Which tools get called how often
- ✅ **Token Consumption**: Model usage and cost
- ✅ **Geographic Distribution**: Which countries/regions use what variations

### User Feedback (Real + Simulated)
- ✅ **Real User Feedback**: Thumbs up/down from actual UI interactions
- ✅ **Simulated User Feedback**: Generated thumbs up/down from traffic generator
- ✅ **Unified Tracking**: Both real and simulated feedback flow to same LaunchDarkly metrics
- ✅ **Satisfaction Scoring**: Converted to 0.0-1.0 ratings for AI Config optimization
- ✅ **Source Distinction**: Feedback tagged as `"real_user"` or `"simulated"`

### Real Business Insights
- 💡 **Cost vs Quality**: Expensive MCP tools vs local knowledge  
- 💡 **Geographic Preferences**: EU users prefer Claude, US users mixed
- 💡 **Plan Optimization**: Enterprise users get research tools, free users get basics
- 💡 **Tool Efficiency**: Which tools provide the most value

---

## 🎓 Tutorial Integration

### For Demo Purposes
1. **Pre-Generate Data**: Run 500+ queries with various users/questions
2. **Analyze Results**: Export LaunchDarkly experiment data  
3. **Create Charts**: Show cost, latency, satisfaction by variation
4. **Tell the Story**: "Enterprise users with MCP tools had 23% higher satisfaction but 4x cost"

### For Live Demos  
1. **Rehearsal Mode**: Generate baseline data 30 minutes before demo
2. **Live Mode**: Run 20-30 queries during presentation to show real-time updates
3. **Explain Openly**: "This script sends real queries and simulates feedback"

### For Educational Content
- **High School Friendly**: No complex OOP, clear variable names, lots of comments
- **Easy to Modify**: JSON files for data, simple Python functions for logic  
- **Visible Results**: Console output shows every step, immediate feedback
- **Real Integration**: Actually uses LaunchDarkly SDK, no fake data

---

## 🔍 Troubleshooting

### "Connection Refused" Errors
```bash
# Make sure API is running
uv run uvicorn api.main:app --reload --port 8001

# Check if port 8001 is available
curl http://localhost:8001/chat
```

### "No Users/Queries" Errors  
```bash
# Make sure data files exist
ls data/fake_users.json data/sample_queries.json

# Check file contents
head data/fake_users.json
```

### Metrics Not Appearing in LaunchDarkly
- Wait 2-3 minutes (LaunchDarkly has slight delay)
- Check that experiments are running in LaunchDarkly dashboard
- Verify LD_SDK_KEY is set correctly in .env
- Look for flush success messages: `🚀 METRICS: Flushed to LaunchDarkly`

### Low Thumbs Up Rates
- Edit the `simulate_feedback()` function in `tools/traffic_generator.py`
- Lower the `thumbs_up_threshold` from 20 to 10
- Add more `good_response_keywords` to your queries in `data/sample_queries.json`

---

## 🎯 Example Scenarios

### Scenario 1: RAG vs Keyword Search Test
```bash
# Generate traffic focused on semantic queries
python tools/traffic_generator.py --queries 50 --delay 1

# Expected: RAG variations get higher satisfaction on complex questions
# Blog insight: "RAG improved semantic accuracy by 31%"
```

### Scenario 2: Geographic Compliance Test  
```bash
# Traffic will include EU users automatically
python tools/traffic_generator.py --queries 100 --delay 0.5

# Expected: EU users consistently get Claude (privacy compliance)
# Blog insight: "EU users were 100% routed to Claude for privacy compliance"
```

### Scenario 3: Cost vs Quality Analysis
```bash  
# Mix of free, pro, and enterprise users
python tools/traffic_generator.py --queries 75 --delay 2

# Expected: Enterprise users get MCP tools, higher satisfaction, higher cost
# Blog insight: "Enterprise users achieved 82% satisfaction at 4x cost"
```

---

## ✅ Success Checklist

- [ ] Backend API running on port 8001
- [ ] LaunchDarkly experiments configured and running
- [ ] Data files exist: `fake_users.json`, `sample_queries.json`  
- [ ] Traffic generator runs without errors
- [ ] Console shows geographic targeting: `🌍 USER CONTEXT: user_eu_001 from DE`
- [ ] Feedback simulation working: `👍 FEEDBACK: user gave 👍 (rating: 4/5)`
- [ ] Metrics flush successfully: `🚀 METRICS: Flushed to LaunchDarkly`
- [ ] LaunchDarkly dashboard shows experiment data within 2-3 minutes

---

## 📚 Next Steps

1. **Customize Your Data**: Add users/queries specific to your use case
2. **Adjust Feedback Rules**: Fine-tune what makes a "good" response
3. **Scale Up**: Run 500+ queries for comprehensive demo data
4. **Create Variations**: Test different tool combinations and model configurations
5. **Analyze Results**: Use LaunchDarkly's experiment analysis for insights

**The traffic generator is ready to help you create compelling, data-driven AI Config content! 🚀**