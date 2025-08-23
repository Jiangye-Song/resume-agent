#!/usr/bin/env python3

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rag_run import rag_query

async def test_rate_limit_handling():
    """测试速率限制错误处理"""
    
    print("🧪 测试速率限制错误处理...")
    print("="*60)
    
    # 执行一个简单的查询来触发速率限制错误
    result = await rag_query("TypeScript projects")
    
    print(f"\n📝 返回结果:\n{result}")

if __name__ == "__main__":
    asyncio.run(test_rate_limit_handling())