"""
Utilities for migrating projects from Postgres (Neon) into Upstash Vector.

Provides an async `migrate_projects_async()` function that reads `projects` table
and upserts each project into Upstash Vector. Returns a stats dict.

This module is usable from serverless endpoints (async) or CLI scripts via
`asyncio.run(migrate_projects_async())`.
"""
import os
import json
import asyncio
from dotenv import load_dotenv

load_dotenv()

try:
    import asyncpg
except Exception:
    asyncpg = None

from upstash_vector import Index


async def migrate_projects_async():
    """Read projects from Postgres and upsert to Upstash Vector.

    Returns a dict: { total, upserted, errors }
    """
    DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('DATABASE_URL_UNPOOLED')
    UPSTASH_VECTOR_REST_URL = os.getenv('UPSTASH_VECTOR_REST_URL')
    UPSTASH_VECTOR_REST_TOKEN = os.getenv('UPSTASH_VECTOR_REST_TOKEN')

    if not DATABASE_URL:
        raise RuntimeError('DATABASE_URL not set')
    if asyncpg is None:
        raise RuntimeError('asyncpg is not installed')
    if not UPSTASH_VECTOR_REST_URL or not UPSTASH_VECTOR_REST_TOKEN:
        raise RuntimeError('Upstash configuration missing')

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        rows = await conn.fetch('SELECT data FROM projects ORDER BY id')
        items = []
        for r in rows:
            d = r['data']
            if isinstance(d, str):
                try:
                    d = json.loads(d)
                except Exception:
                    # keep as string fallback
                    d = {'text': str(d)}
            items.append(d)
    finally:
        await conn.close()

    total = len(items)
    upserted = 0
    errors = []

    index = Index(url=UPSTASH_VECTOR_REST_URL, token=UPSTASH_VECTOR_REST_TOKEN)

    for item in items:
        try:
            title = item.get('title') if isinstance(item, dict) else None
            summary = item.get('summary') if isinstance(item, dict) else None
            if not title:
                title = item.get('text') if isinstance(item, dict) else str(item)
            if not summary:
                summary = item.get('text') if isinstance(item, dict) else ''

            enriched_text = f"{title}. {summary}" if summary else str(title)
            pid = f"project:{item.get('id') or title}"
            metadata = {
                'title': title,
                'summary': summary,
                'tags': item.get('tags', []) if isinstance(item, dict) else [],
                'project-detail-url': item.get('url', '') if isinstance(item, dict) else '',
                'source': 'project',
                # store raw data but be cautious about size; this is optional
                'data': item if isinstance(item, dict) else {'text': str(item)}
            }

            # Use to_thread to call the synchronous SDK method without blocking the loop
            await asyncio.to_thread(index.upsert, [(str(pid), enriched_text, metadata)])
            upserted += 1
        except Exception as e:
            errors.append({'id': item.get('id') if isinstance(item, dict) else None, 'error': str(e)})

    return {
        'total': total,
        'upserted': upserted,
        'errors': errors,
    }


def migrate_projects():
    """Synchronous wrapper for CLI usage."""
    return asyncio.run(migrate_projects_async())
