# AI Config Evaluators

This directory contains evaluators for testing AI Configs with the `ld-aic-cicd` framework.

## What is an Evaluator?

An evaluator is a class that implements the `LocalEvaluator` interface from `ld-aic-cicd`. It's responsible for:
1. Calling your application's API with test inputs
2. Returning the AI-generated responses
3. Allowing the judge to score those responses

## Using the Local Evaluator

### For GitHub Actions

The workflow uses `evaluators/local_evaluator.py` which is configured to connect to your API running on `http://127.0.0.1:8000`.

**If your API runs on a different port**, update line 36 in `local_evaluator.py`:

```python
def __init__(self, api_url: str = "http://127.0.0.1:YOUR_PORT"):
```

### For Local Testing

When running tests locally with `./run_ai_config_tests.sh`, the evaluator will connect to your API at `http://127.0.0.1:8000`.

The script automatically:
1. Starts your API on port 8000
2. Runs the tests with the evaluator
3. Stops the API when done

## Creating Your Own Evaluator

If you need to customize the evaluator (different endpoint, authentication, etc.):

1. **Copy the template:**
   ```bash
   cp evaluators/local_evaluator.py evaluators/my_custom_evaluator.py
   ```

2. **Modify the class:**
   - Change the `__init__` method to set your API URL
   - Update the `evaluate_case` method if your API has different request/response formats
   - Add authentication headers if needed

3. **Update the workflow:**
   In `.github/workflows/ai-config-validation.yml`, change:
   ```yaml
   --evaluator evaluators.local_evaluator:AgentsDemoEvaluator
   ```
   to:
   ```yaml
   --evaluator evaluators.my_custom_evaluator:YourEvaluatorClass
   ```

## Required Dependencies

The evaluator requires these packages (already included in `pyproject.toml`):
- `httpx` - For making HTTP requests
- `ld-aic-cicd` - For the base `LocalEvaluator` interface

## Troubleshooting

**Connection errors in CI:**
- Make sure the API is started in the same workflow step as the tests
- Verify the port matches between `uvicorn` startup and evaluator URL
- Use `127.0.0.1` instead of `localhost` for better CI compatibility

**Import errors:**
- Ensure `ld-aic-cicd` is installed: `uv pip install git+https://...`
- Check that `PYTHONPATH` includes your project directory

**API not responding:**
- Add a health check endpoint (`/health`) to your API
- Verify the API starts successfully by checking logs
