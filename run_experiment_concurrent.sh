#!/bin/bash
# Run concurrent traffic generator with full logging

# Create logs directory if it doesn't exist
mkdir -p logs

# Generate timestamp for log file
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="logs/concurrent_experiment_${TIMESTAMP}.log"

echo "🚀 Starting Concurrent Traffic Generator Experiment"
echo "=================================================="
echo "Queries: 200"
echo "Concurrency: 10 parallel requests"
echo "Timeout: 2000 seconds (33 min) per request"
echo "Log file: ${LOG_FILE}"
echo "=================================================="
echo ""
echo "With 10 concurrent requests, this should complete in ~40-60 minutes"
echo "(instead of 66+ hours with sequential requests!)"
echo ""
echo "Press Ctrl+C to stop at any time"
echo ""

# Run concurrent traffic generator and log everything (unbuffered output)
uv run python -u tools/concurrent_traffic_generator.py --queries 200 --concurrency 10 2>&1 | tee "${LOG_FILE}"

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
echo "  grep 'Success' ${LOG_FILE} | wc -l"
echo "=================================================="

