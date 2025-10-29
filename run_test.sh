#!/bin/bash
# Simple test runner script
set -a
source .env
set +a

export PYTHONPATH=$(pwd)

uv run ld-aic test \
  --config-keys "supervisor-agent,support-agent,security-agent" \
  --environment production \
  --evaluation-dataset test_data/ai_config_evaluation.yaml \
  --evaluator evaluators.local_evaluator:AgentsDemoEvaluator \
  --report test-report.json
