"""Test script for AI Agent with various query types"""

import asyncio
import httpx
import json


BASE_URL = "http://localhost:7860"


async def test_query(question: str, use_agent: bool = True):
    """Send a query and print the response"""
    print(f"\n{'='*80}")
    print(f"QUERY: {question}")
    print(f"MODE: {'AI Agent' if use_agent else 'Legacy RAG'}")
    print(f"{'='*80}")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{BASE_URL}/api/chat",
                json={"question": question, "use_agent": use_agent}
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"\nANSWER:\n{data.get('answer', 'No answer')}")
                print(f"\nMODE: {data.get('mode', 'unknown')}")
                if data.get('tools_used'):
                    print(f"TOOLS USED: {', '.join(data['tools_used'])}")
            else:
                print(f"ERROR: Status {response.status_code}")
                print(response.text)
        except Exception as e:
            print(f"ERROR: {str(e)}")


async def main():
    """Run test queries"""
    
    print("\n" + "="*80)
    print("AI AGENT TEST SUITE")
    print("="*80)
    
    # Test 1: Temporal query (should use get_records_by_date)
    await test_query("What is my most recent project?")
    await asyncio.sleep(2)
    
    # Test 2: Semantic query (should use rag_search_by_domain)
    await test_query("Tell me about machine learning projects")
    await asyncio.sleep(2)
    
    # Test 3: Tag filter query (should use filter_records)
    await test_query("Show me Python projects")
    await asyncio.sleep(2)
    
    # Test 4: Statistics query (should use get_statistics)
    await test_query("How many projects do I have?")
    await asyncio.sleep(2)
    
    # Test 5: Combined query (should use multiple tools)
    await test_query("What are my most recent Python projects from 2024?")
    await asyncio.sleep(2)
    
    # Test 6: Detail query (should use date tool + detail tool)
    await test_query("What's the latest project and give me full details about it?")
    await asyncio.sleep(2)
    
    # Test 7: Technology distribution (should use get_statistics)
    await test_query("What are my most used technologies?")
    await asyncio.sleep(2)
    
    print("\n" + "="*80)
    print("TEST SUITE COMPLETED")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
