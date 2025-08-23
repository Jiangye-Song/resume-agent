#!/usr/bin/env python3

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rag_run import rag_query

async def test_new_filtering():
    """测试新的优先级过滤逻辑"""
    
    test_queries = [
        "TypeScript projects",
        "TypeScript internship", 
        "web development projects",
        "game development",
        "AI projects"
    ]
    
    for query in test_queries:
        print(f"\n{'='*80}")
        print(f"🔍 测试查询: '{query}'")
        print(f"{'='*80}")
        
        # 执行查询
        result = await rag_query(query)
        
        print(f"\n📝 LLM回答:\n{result}")
        print(f"\n{'='*80}\n")

if __name__ == "__main__":
    asyncio.run(test_new_filtering())