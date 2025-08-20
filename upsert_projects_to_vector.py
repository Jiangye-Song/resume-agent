"""
Read projects from Postgres and upsert them into Upstash Vector with metadata.

Usage:
    python upsert_projects_to_vector.py

It reads DATABASE_URL and UPSTASH_VECTOR_REST_URL/UPSTASH_VECTOR_REST_TOKEN from environment.
"""
import os
import json
import asyncio
import asyncpg
from dotenv import load_dotenv
from upstash_vector import Index

# Load environment variables from .env (if present)
load_dotenv()

DB_URL = os.environ.get('DATABASE_URL') or os.environ.get('DATABASE_URL_UNPOOLED')
UPSTASH_VECTOR_REST_URL = os.environ.get('UPSTASH_VECTOR_REST_URL')
UPSTASH_VECTOR_REST_TOKEN = os.environ.get('UPSTASH_VECTOR_REST_TOKEN')

async def run():
    if not DB_URL:
        print('DATABASE_URL not set; aborting')
        return
    if not UPSTASH_VECTOR_REST_URL or not UPSTASH_VECTOR_REST_TOKEN:
        print('UPSTASH_VECTOR_REST_URL / UPSTASH_VECTOR_REST_TOKEN not set; aborting')
        return

    conn = await asyncpg.connect(DB_URL)
    try:
        rows = await conn.fetch('SELECT data FROM projects ORDER BY id')
        items = []
        for r in rows:
            d = r['data']
            if isinstance(d, str):
                d = json.loads(d)
            items.append(d)

        if not items:
            print('No projects found to upsert')
            return

        index = Index(url=UPSTASH_VECTOR_REST_URL, token=UPSTASH_VECTOR_REST_TOKEN)
        for item in items:
            title = item.get('title') or 'Untitled'
            summary = item.get('summary') or item.get('text', '')
            enriched_text = f"{title}. {summary}"
            metadata = {
                'title': title,
                'summary': summary,
                'source': 'project'
            }
            pid = item.get('id') or title
            try:
                await asyncio.to_thread(index.upsert, [(str(pid), enriched_text, metadata)])
                print('Upserted', pid)
            except Exception as e:
                print('Failed to upsert', pid, e)
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(run())
