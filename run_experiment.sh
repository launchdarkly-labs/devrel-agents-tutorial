#!/bin/bash
# Run traffic generator with full logging

# Create logs directory if it doesn't exist
mkdir -p logs

# Generate timestamp for log file
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="logs/traffic_experiment_${TIMESTAMP}.log"

echo "🚀 Starting Traffic Generator Experiment"
echo "=================================================="
echo "Queries: 200"
echo "Delay: 2 seconds between requests"
echo "Timeout: 500 seconds per request"
echo "Log file: ${LOG_FILE}"
echo "=================================================="
echo ""
echo "Press Ctrl+C to stop at any time"
echo ""

# Run traffic generator and log everything
uv run python tools/traffic_generator.py --queries 200 --delay 2 2>&1 | tee "${LOG_FILE}"

echo ""
echo "=================================================="
echo "✅ Experiment complete!"
echo "Log saved to: ${LOG_FILE}"
echo ""
echo "To view logs later:"
echo "  cat ${LOG_FILE}"
echo ""
echo "To search for cost issues:"
echo "  grep 'COST SKIPPED' ${LOG_FILE}"
echo "  grep 'COST TRACKING' ${LOG_FILE}"
echo "=================================================="

