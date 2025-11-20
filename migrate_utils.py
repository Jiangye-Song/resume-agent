"""
Utilities for migrating records from Postgres (Neon) into Upstash Vector.

Provides an async `migrate_records_async()` function that reads `records` table
and upserts each record into Upstash Vector with comprehensive metadata concatenation.
Returns a stats dict.

This module is usable from serverless endpoints (async) or CLI scripts via
`asyncio.run(migrate_records_async())`.
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


async def migrate_records_async():
    """Read records from Postgres and upsert to Upstash Vector with enhanced metadata.

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
        # Read from records table with new schema including facts
        rows = await conn.fetch('''
            SELECT id, type, title, summary, tags, detail_site, additional_url, 
                   start_date, end_date, priority, facts
            FROM records 
            ORDER BY priority DESC, type, id
        ''')
        
        records = []
        for r in rows:
            record = {
                'id': r['id'],
                'type': r['type'],
                'title': r['title'],
                'summary': r['summary'],
                'tags': list(r['tags']) if r['tags'] else [],
                'detail_site': r['detail_site'],
                'additional_url': r['additional_url'] if r['additional_url'] else [],
                'start_date': r['start_date'].isoformat() if r['start_date'] else None,
                'end_date': r['end_date'].isoformat() if r['end_date'] else None,
                'priority': r['priority'],
                'facts': list(r['facts']) if r['facts'] else []
            }
            records.append(record)
    finally:
        await conn.close()

    total = len(records)
    upserted = 0
    errors = []

    index = Index(url=UPSTASH_VECTOR_REST_URL, token=UPSTASH_VECTOR_REST_TOKEN)

    for record in records:
        try:
            # Build comprehensive enriched text with ALL metadata
            enriched_parts = []
            
            # 1. Title (highest semantic weight)
            if record.get('title'):
                enriched_parts.append(record['title'])
            
            # 2. Summary (detailed content)
            if record.get('summary'):
                enriched_parts.append(record['summary'])
            
            # 3. Facts (key information points)
            if record.get('facts'):
                facts_str = '. '.join(record['facts'])
                enriched_parts.append(f"Key facts: {facts_str}")
            
            # 4. Tags (keywords for semantic search)
            if record.get('tags'):
                tags_str = ' '.join(record['tags'])
                enriched_parts.append(f"Technologies: {tags_str}")
            
            # 5. Detail site URL
            if record.get('detail_site'):
                enriched_parts.append(f"Website: {record['detail_site']}")
            
            # 6. Additional URLs with labels
            if record.get('additional_url'):
                for url_pair in record['additional_url']:
                    if len(url_pair) == 2:
                        label, url = url_pair
                        enriched_parts.append(f"{label.capitalize()}: {url}")
            
            # 7. Temporal information
            date_parts = []
            if record.get('start_date'):
                date_parts.append(f"from {record['start_date']}")
            if record.get('end_date'):
                date_parts.append(f"to {record['end_date']}")
            if date_parts:
                enriched_parts.append(f"Duration {' '.join(date_parts)}")
            
            # 8. Type/Category
            record_type = record.get('type', 'project')
            enriched_parts.append(f"Category: {record_type}")
            
            # Join all parts into enriched text
            enriched_text = ". ".join(enriched_parts) + "."
            
            # Build metadata for storage including facts
            metadata = {
                'id': record['id'],
                'type': record_type,
                'title': record.get('title', 'untitled'),
                'summary': record.get('summary', ''),
                'facts': record.get('facts', []),
                'tags': record.get('tags', []),
                'detail_site': record.get('detail_site', ''),
                'additional_url': record.get('additional_url', []),
                'start_date': record.get('start_date'),
                'end_date': record.get('end_date'),
                'priority': record.get('priority', 3),
                'source': record_type  # Use type as source
            }
            
            # Create namespaced ID: {type}:{id}
            vector_id = f"{record_type}:{record['id']}"
            
            # Upsert to vector DB
            await asyncio.to_thread(index.upsert, [(str(vector_id), enriched_text, metadata)])
            upserted += 1
            
            print(f"✅ Upserted {vector_id}: {record.get('title', 'untitled')[:50]}...")
            
        except Exception as e:
            error_msg = {'id': record.get('id'), 'type': record.get('type'), 'error': str(e)}
            errors.append(error_msg)
            print(f"❌ Error upserting {record.get('id')}: {str(e)}")

    return {
        'total': total,
        'upserted': upserted,
        'errors': errors,
    }


def migrate_records():
    """Synchronous wrapper for CLI usage."""
    return asyncio.run(migrate_records_async())


# Backward compatibility aliases
migrate_projects_async = migrate_records_async
migrate_projects = migrate_records
