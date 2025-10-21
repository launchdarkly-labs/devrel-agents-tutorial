#!/usr/bin/env python3
"""
LocalEvaluator Implementation for agents-demo Project

This evaluator makes HTTP requests to the agents-demo FastAPI backend
to generate AI responses using LaunchDarkly AI configs.

CONFIGURATION:
    - API URL: Defaults to http://127.0.0.1:8000
    - If your API runs on a different port, update line 36 below
    - The GitHub Actions workflow starts the API on port 8000

Usage:
    1. Start the agents-demo backend: `uvicorn api.main:app --reload --port 8000`
    2. Run tests: `ld-aic test --evaluator evaluators.local_evaluator:AgentsDemoEvaluator`
"""
import os
import time
import httpx
from typing import Dict, Any
from dotenv import load_dotenv

# Import from ld-aic-cicd package
try:
    from src.evaluator import LocalEvaluator, EvaluationResult
except ImportError:
    # Fallback if running standalone - these should be available from installed package
    import sys
    from pathlib import Path
    # Try to import from installed ld-aic-cicd package
    try:
        from src.evaluator import LocalEvaluator, EvaluationResult
    except:
        raise ImportError("Could not import LocalEvaluator and EvaluationResult. Make sure ld-aic-cicd is installed.")

load_dotenv()


class AgentsDemoEvaluator(LocalEvaluator):
    """
    Evaluator for the agents-demo multi-agent system.

    Makes HTTP POST requests to the /chat endpoint with LaunchDarkly context attributes.
    """

    def __init__(self, api_url: str = "http://127.0.0.1:8000"):
        """
        Initialize the evaluator.

        Args:
            api_url: Base URL of the agents-demo API (default: http://localhost:8000)
        """
        self.api_url = api_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=60.0)  # 60 second timeout for agent responses

    async def evaluate_case(
        self,
        config_key: str,
        test_input: str,
        context_attributes: Dict[str, Any]
    ) -> EvaluationResult:
        """
        Generate response by calling the agents-demo /chat endpoint.

        The agents-demo system uses LaunchDarkly internally, so we just need to
        pass the context attributes and let the backend handle config resolution.
        """
        try:
            start_time = time.time()

            # Build request payload
            # The agents-demo /chat endpoint expects:
            # {
            #   "message": "user question",
            #   "user_id": "user-123",  # optional
            #   "context": {...}        # LaunchDarkly context attributes
            # }
            payload = {
                "message": test_input,
                "user_id": context_attributes.get("key", "test-user"),
                "context": context_attributes
            }

            url = f"{self.api_url}/chat"
            print(f"DEBUG: Calling {url} with payload: {payload}")

            # Make HTTP request to the chat endpoint
            response = await self.client.post(url, json=payload)
            print(f"DEBUG: Got response status: {response.status_code}")

            latency_ms = (time.time() - start_time) * 1000

            # Check if request was successful
            if response.status_code != 200:
                return EvaluationResult(
                    response="",
                    latency_ms=latency_ms,
                    variation="error",
                    config_key=config_key,
                    error=f"HTTP {response.status_code}: {response.text}"
                )

            # Parse response
            # Expected format: {"response": "...", "metadata": {...}}
            response_data = response.json()
            response_text = response_data.get("response", "")
            metadata = response_data.get("metadata", {})

            # Extract which agent/variation was used from metadata
            variation = metadata.get("agent", "unknown")
            agent_used = metadata.get("final_agent", variation)

            return EvaluationResult(
                response=response_text,
                latency_ms=latency_ms,
                variation=variation,
                config_key=config_key,
                metadata={
                    "agent_used": agent_used,
                    "http_status": response.status_code,
                    **metadata  # Include all metadata from response
                }
            )

        except httpx.TimeoutException:
            return EvaluationResult(
                response="",
                latency_ms=60000,  # Timeout duration
                variation="error",
                config_key=config_key,
                error="Request timeout (60s)"
            )

        except Exception as e:
            import traceback
            error_details = f"Error calling API: {type(e).__name__}: {str(e)}\nTraceback: {traceback.format_exc()}"
            return EvaluationResult(
                response="",
                latency_ms=0,
                variation="error",
                config_key=config_key,
                error=error_details
            )

    async def cleanup(self):
        """Close the HTTP client"""
        await self.client.aclose()


# Example usage
async def main():
    """Example of using the evaluator directly"""
    from rich.console import Console

    console = Console()

    # Create evaluator
    evaluator = AgentsDemoEvaluator()

    # Test cases
    test_cases = [
        {
            "config_key": "support-agent",
            "input": "What is LaunchDarkly?",
            "context": {"user_type": "customer", "region": "US"}
        },
        {
            "config_key": "security-agent",
            "input": "My email is john@example.com",
            "context": {"user_type": "customer", "region": "EU"}
        },
        {
            "config_key": "supervisor-agent",
            "input": "Can you help me with feature flags?",
            "context": {"user_type": "developer", "plan": "enterprise"}
        }
    ]

    console.print("[bold cyan]Testing agents-demo Evaluator[/bold cyan]\n")

    for test in test_cases:
        console.print(f"[bold]Config:[/bold] {test['config_key']}")
        console.print(f"[bold]Input:[/bold] {test['input']}")
        console.print(f"[bold]Context:[/bold] {test['context']}")

        result = await evaluator.evaluate_case(
            config_key=test["config_key"],
            test_input=test["input"],
            context_attributes=test["context"]
        )

        if result.error:
            console.print(f"[red]Error: {result.error}[/red]\n")
        else:
            console.print(f"[green]Response ({result.latency_ms:.0f}ms):[/green]")
            console.print(f"[dim]{result.response[:200]}...[/dim]")
            console.print(f"[dim]Variation: {result.variation}[/dim]\n")

    await evaluator.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
