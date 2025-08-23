"""
Script to update the system prompt in the database.

Usage:
    python update_system_prompt.py

This will update the system prompt stored in the database. The RAG system will
automatically pick up the new prompt in new conversations (within 5 minutes due to caching).
"""
import os
import json
import asyncio
import asyncpg
from dotenv import load_dotenv

load_dotenv()

# The system prompt you want to set
NEW_SYSTEM_PROMPT = '''You are a virtual assistant representing Jiangye, a job seeker actively looking for software engineering opportunities. Jiangye was an international student with bachelor degree of Computer Science in Monash University, and master degree of Information technology in UNSW, currently have full working rights. Your primary goal is to help recruiters, hiring managers, or collaborators understand Jiangye's background, technical skills, and project experience.

You are knowledgeable about Jiangye's past projects stored in a vector database. If a project's `end_date` is missing, treat it as an ongoing project (i.e., still active). When asked about projects, technologies, or experience, refer to available data and answer clearly and concisely.

You should sound professional, friendly, and confident, like Jiangye himself presenting his work.'''

async def update_system_prompt():
    DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('DATABASE_URL_UNPOOLED')
    if not DATABASE_URL:
        print('ERROR: DATABASE_URL or DATABASE_URL_UNPOOLED not set')
        return

    print('Connecting to database...')
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        # Try to create a config table first (if it doesn't exist)
        try:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            ''')
            print('✅ Config table ensured')
            
            # Insert/update the system prompt
            await conn.execute('''
                INSERT INTO config (key, value, updated_at) 
                VALUES ('system_prompt', $1, NOW())
                ON CONFLICT (key) 
                DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
            ''', NEW_SYSTEM_PROMPT)
            print('✅ System prompt updated in config table')
            
        except Exception as e:
            print(f'Config table approach failed: {e}')
            print('Falling back to projects table approach...')
            
            # Fallback: use projects table with special record
            system_prompt_data = {
                'prompt': NEW_SYSTEM_PROMPT,
                'type': 'system_config',
                'updated_at': 'now'
            }
            
            await conn.execute('''
                INSERT INTO projects (id, title, summary, tags, url, data)
                VALUES ('system_prompt', 'System Prompt Config', 'AI Assistant System Prompt', ARRAY['config'], '', $1)
                ON CONFLICT (id) 
                DO UPDATE SET data = EXCLUDED.data, title = EXCLUDED.title
            ''', json.dumps(system_prompt_data))
            print('✅ System prompt updated in projects table')
            
    finally:
        await conn.close()

    print('\n🎉 System prompt updated successfully!')
    print('💡 The new prompt will be used in new conversations within 5 minutes (due to caching).')
    print('💡 To use the new prompt immediately, restart your server or wait for cache to expire.')

if __name__ == '__main__':
    asyncio.run(update_system_prompt())