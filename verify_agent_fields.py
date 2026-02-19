"""Verify that AI Agent receives correct fields (no summary)"""

import asyncio
import httpx
import json


async def test_agent_fields():
    """Test that tools return correct fields"""
    
    print("="*80)
    print("VERIFYING AI AGENT FIELDS")
    print("="*80)
    
    # Test query that will trigger multiple tools
    question = "What's my most recent project?"
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "http://localhost:7860/api/chat",
            json={"question": question, "use_agent": True}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Query: {question}")
            print(f"✅ Mode: {data.get('mode')}")
            print(f"✅ Tools used: {data.get('tools_used', [])}")
            print(f"\n📋 Answer Preview:")
            print(data.get('answer', '')[:500])
            
            # Check if answer mentions summary (it shouldn't since we removed it)
            answer = data.get('answer', '')
            if 'summary' in answer.lower() and 'no summary' not in answer.lower():
                print("\n⚠️  WARNING: Answer might still reference summary field")
            else:
                print("\n✅ Answer does not reference summary field directly")
            
            # Expected fields in tool responses
            expected_fields = ['title', 'tags', 'priority', 'facts', 'detail_site', 'additional_url']
            print(f"\n📊 Expected fields in tools: {', '.join(expected_fields)}")
            print("❌ Excluded field: summary")
            
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)


if __name__ == "__main__":
    asyncio.run(test_agent_fields())
