"""Test Semantic Scholar with timeout controls"""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from tools_impl.mcp_research_tools import get_mcp_research_tools

async def test_with_timeout(timeout_seconds: int):
    """Test Semantic Scholar with a specific timeout"""
    print(f"\n{'='*60}")
    print(f"Testing with {timeout_seconds} second timeout")
    print(f"{'='*60}\n")

    try:
        # Initialize MCP tools
        print("Initializing MCP tools...")
        mcp_tools = await get_mcp_research_tools()

        # Get Semantic Scholar tool
        semantic_tool = mcp_tools.get_tool("semantic_scholar")
        if not semantic_tool:
            print("❌ Semantic Scholar tool not found!")
            print(f"Available tools: {mcp_tools.get_available_tools()}")
            return False

        print(f"✅ Semantic Scholar tool found: {semantic_tool.name}")
        print(f"Description: {semantic_tool.description}\n")

        # Test with timeout
        print(f"Executing search with {timeout_seconds}s timeout...")
        print(f"Query: 'transformer models natural language processing'")
        print(f"Num results: 5\n")

        start_time = asyncio.get_event_loop().time()

        try:
            # Run with timeout
            result = await asyncio.wait_for(
                semantic_tool.ainvoke({
                    "query": "transformer models natural language processing",
                    "num_results": 5
                }),
                timeout=timeout_seconds
            )

            elapsed = asyncio.get_event_loop().time() - start_time
            print(f"\n✅ Completed in {elapsed:.2f} seconds")
            print(f"Results returned: {len(result) if isinstance(result, list) else 'N/A'}")
            return True

        except asyncio.TimeoutError:
            elapsed = asyncio.get_event_loop().time() - start_time
            print(f"\n⏱️  TIMEOUT after {elapsed:.2f} seconds")
            print(f"Expected timeout: {timeout_seconds}s")
            return False

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        print(traceback.format_exc())
        return False

async def main():
    """Run timeout tests"""
    print("\n" + "="*60)
    print("SEMANTIC SCHOLAR TIMEOUT TEST")
    print("="*60)

    # Test 1: 30 second timeout (should fail with rate limiting)
    print("\nTest 1: 30 second timeout (likely to hit rate limits)")
    result_30s = await test_with_timeout(30)

    # Wait a bit between tests
    await asyncio.sleep(2)

    # Test 2: 120 second timeout (should complete despite rate limiting)
    print("\n\nTest 2: 120 second timeout (should handle rate limits)")
    result_120s = await test_with_timeout(120)

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"30s timeout:  {'PASSED' if result_30s else 'FAILED (EXPECTED)'}")
    print(f"120s timeout: {'PASSED' if result_120s else 'FAILED'}")
    print("\nRecommendation: Use 120s timeout for Semantic Scholar to handle rate limiting")

if __name__ == "__main__":
    asyncio.run(main())
