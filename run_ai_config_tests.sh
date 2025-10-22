#!/bin/bash
# Run AI Config tests with explicit config keys and real evaluations
# This script starts the API, runs tests with the evaluator, then stops the API

set -e

# Change to agents-demo directory
cd /Users/ld_scarlett/Documents/Github/agents-demo

echo "Loading environment variables from .env..."
if [ -f .env ]; then
    set -a
    source .env
    set +a
else
    echo "Warning: .env file not found"
fi

# Check if API is already running
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "API already running on port 8000"
    API_WAS_RUNNING=true
else
    echo "Starting agents-demo API..."
    # Use uv run to ensure correct environment
    uv run uvicorn api.main:app --port 8000 > /tmp/agents-demo-api.log 2>&1 &
    API_PID=$!
    API_WAS_RUNNING=false
    echo "Waiting for API to start (PID: $API_PID)..."

    # Wait up to 15 seconds for API to be ready
    for i in {1..15}; do
        if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
            echo "API is ready!"
            break
        fi
        if ! kill -0 $API_PID 2>/dev/null; then
            echo "ERROR: API process died. Check /tmp/agents-demo-api.log for details"
            cat /tmp/agents-demo-api.log
            exit 1
        fi
        sleep 1
    done

    # Final check
    if ! lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        echo "ERROR: API failed to start after 15 seconds"
        cat /tmp/agents-demo-api.log
        exit 1
    fi
fi

echo "Installing/updating ld-aic-cicd package..."
cd /Users/ld_scarlett/Documents/Github/ld-aic-cicd
uv pip install -e .

echo ""
echo "Running AI Config test suite with real evaluations..."
# IMPORTANT: Run from agents-demo directory so logs are created here
cd /Users/ld_scarlett/Documents/Github/agents-demo

# Run with the evaluator for real API calls
/Users/ld_scarlett/Documents/Github/agents-demo/.venv/bin/python -m src.cli test \
  --config-keys "supervisor-agent,support-agent,security-agent" \
  --environment production \
  --evaluation-dataset /Users/ld_scarlett/Documents/Github/agents-demo/test_data/ai_config_evaluation.yaml \
  --evaluator examples.agents_demo_evaluator:AgentsDemoEvaluator \
  --report /Users/ld_scarlett/Documents/Github/agents-demo/test-report.json \
  --skip-sync

# Stop the API if we started it
if [ "$API_WAS_RUNNING" = false ]; then
    echo ""
    echo "Stopping API..."
    kill $API_PID 2>/dev/null || true
fi

# Return to agents-demo directory
cd /Users/ld_scarlett/Documents/Github/agents-demo

echo ""
echo "Test complete! Check test-report.json for results."
