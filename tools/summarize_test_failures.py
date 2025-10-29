#!/usr/bin/env python3
"""
Summarize test failures from judge evaluation logs and API server logs.
Used in GitHub Actions to provide human-readable failure summaries.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any
import re


def parse_judge_logs(logs_dir: Path) -> List[Dict[str, Any]]:
    """Parse all judge evaluation JSONL files in logs directory."""
    evaluations = []

    if not logs_dir.exists():
        print(f"⚠️  Judge logs directory not found: {logs_dir}")
        return []

    # Find all JSONL files
    jsonl_files = list(logs_dir.glob("*.jsonl"))

    if not jsonl_files:
        print(f"⚠️  No JSONL files found in {logs_dir}")
        return []

    for jsonl_file in jsonl_files:
        print(f"📄 Reading {jsonl_file.name}")
        with open(jsonl_file, 'r') as f:
            for line in f:
                if line.strip():
                    try:
                        evaluations.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        print(f"⚠️  Failed to parse line in {jsonl_file.name}: {e}")

    return evaluations


def parse_api_logs(log_file: Path) -> List[str]:
    """Extract relevant error messages from API server logs."""
    errors = []

    if not log_file.exists():
        print(f"⚠️  API log file not found: {log_file}")
        return []

    print(f"📄 Reading {log_file.name}")

    # Patterns to look for
    error_patterns = [
        r"ERROR:.*",
        r"Exception:.*",
        r"Traceback.*",
        r"Failed.*",
        r"Connection error.*",
        r"PII PRE-SCREENING ERROR:.*",
        r"SEARCH ERROR:.*",
    ]

    combined_pattern = re.compile('|'.join(error_patterns), re.IGNORECASE)

    with open(log_file, 'r') as f:
        for line in f:
            if combined_pattern.search(line):
                errors.append(line.strip())

    return errors


def summarize_failures(evaluations: List[Dict[str, Any]]) -> None:
    """Print human-readable summary of test failures."""

    print("\n" + "="*80)
    print("🔍 TEST FAILURE SUMMARY")
    print("="*80 + "\n")

    # Separate passed and failed tests (using new field names)
    # The new format uses 'passed' boolean and 'aggregate_score'
    passed = [e for e in evaluations if e.get('passed', False)]
    failed = [e for e in evaluations if not e.get('passed', True)]

    print(f"📊 Overall Results:")
    print(f"   ✅ Passed: {len(passed)}/{len(evaluations)}")
    print(f"   ❌ Failed: {len(failed)}/{len(evaluations)}")
    print()

    if not failed:
        print("🎉 All tests passed!")
        return

    print("❌ Failed Tests:\n")

    # Group failures by agent/config
    by_agent = {}
    for eval_result in failed:
        # Extract agent from context_attributes or config_key
        agent = eval_result.get('context_attributes', {}).get('agent', 'unknown')
        if agent == 'unknown':
            # Try to extract from config_key (e.g., "support-agent" → "support")
            config_key = eval_result.get('config_key', 'unknown')
            agent = config_key.replace('-agent', '') if '-agent' in config_key else config_key

        if agent not in by_agent:
            by_agent[agent] = []
        by_agent[agent].append(eval_result)

    # Print failures grouped by agent
    for agent, results in sorted(by_agent.items()):
        print(f"\n{'─'*80}")
        print(f"Agent: {agent.upper()}")
        print(f"{'─'*80}\n")

        for result in results:
            # Use new field names from JudgeLogEntry
            test_id = result.get('case_id', 'unknown')
            test_input = result.get('input_prompt', 'N/A')
            aggregate_score = result.get('aggregate_score', 0)
            threshold = result.get('threshold', 7.0)

            print(f"Test ID: {test_id}")
            print(f"Score: {aggregate_score:.2f}/{threshold}")
            print(f"Input: {test_input[:100]}..." if len(test_input) > 100 else f"Input: {test_input}")
            print()

            # Show criterion scores from judge_parsed_scores
            parsed_scores = result.get('judge_parsed_scores', [])
            if parsed_scores:
                print("Criterion Scores:")
                for score_obj in parsed_scores:
                    criterion = score_obj.get('criterion', 'Unknown')
                    score = score_obj.get('score', 0)
                    emoji = "✅" if score >= 7.0 else "❌"
                    print(f"  {emoji} {criterion}: {score:.1f}/10")

                    # Show reasoning for this criterion
                    reasoning = score_obj.get('reasoning', '')
                    if reasoning:
                        print(f"     → {reasoning}")
                print()

            # Show strengths/weaknesses/suggestions
            strengths = result.get('strengths', [])
            weaknesses = result.get('weaknesses', [])
            suggestions = result.get('suggestions', [])

            if strengths:
                print("Strengths:")
                for strength in strengths:
                    print(f"  ✓ {strength}")
                print()

            if weaknesses:
                print("Weaknesses:")
                for weakness in weaknesses:
                    print(f"  ✗ {weakness}")
                print()

            if suggestions:
                print("Suggestions:")
                for suggestion in suggestions:
                    print(f"  💡 {suggestion}")
                print()

            # Show actual AI response (truncated)
            response = result.get('model_response', 'N/A')
            print("AI Response:")
            print(f"  {response[:200]}..." if len(response) > 200 else f"  {response}")
            print()

    print("="*80)


def summarize_api_errors(errors: List[str]) -> None:
    """Print summary of API server errors."""

    if not errors:
        print("\n✅ No API errors detected in server logs\n")
        return

    print("\n" + "="*80)
    print("🔧 API SERVER ERRORS")
    print("="*80 + "\n")

    # Group similar errors
    error_counts = {}
    for error in errors:
        # Extract error type
        error_type = error.split(':')[0] if ':' in error else 'Unknown'
        error_counts[error_type] = error_counts.get(error_type, 0) + 1

    print("Error Types:")
    for error_type, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  • {error_type}: {count} occurrences")
    print()

    print("Recent Errors (last 10):")
    for error in errors[-10:]:
        print(f"  {error}")

    print("\n" + "="*80)


def main():
    """Main entry point for log summarization."""

    # Paths
    judge_logs_dir = Path("logs/judge_evaluations")
    api_log_file = Path("/tmp/agents-demo-api.log")

    print("\n🔍 Analyzing test failures...\n")

    # Parse logs
    evaluations = parse_judge_logs(judge_logs_dir)
    api_errors = parse_api_logs(api_log_file)

    # Print summaries
    if evaluations:
        summarize_failures(evaluations)
    else:
        print("⚠️  No judge evaluation logs found")

    if api_errors:
        summarize_api_errors(api_errors)

    print("\n✨ Summary complete\n")

    # Exit with error code if there were failures
    if evaluations:
        failed_count = sum(1 for e in evaluations if e.get('scores', {}).get('overall', 0) < 0.6)
        if failed_count > 0:
            sys.exit(1)


if __name__ == "__main__":
    main()
