"""
Small helper script to create a `foods` table in Postgres (Neon) and populate it from foods.json.
It uses asyncpg and reads DATABASE_URL from env. If DATABASE_URL is not set, it will exit.

Table schema created:
- id TEXT PRIMARY KEY
- text TEXT
- region TEXT
- type TEXT
- raw JSONB stored in column `data`

Usage:
    python db_migrate.py

"""
import os
import json
import asyncio
import asyncpg

DB_URL = os.environ.get('DATABASE_URL') or os.environ.get('DATABASE_URL_UNPOOLED')
JSON_FILE = 'foods.json'

CREATE_TABLE_SQL = '''
CREATE TABLE IF NOT EXISTS foods (
    id TEXT PRIMARY KEY,
    text TEXT,
    region TEXT,
    type TEXT,
    data JSONB
);
'''

INSERT_SQL = '''
INSERT INTO foods (id, text, region, type, data)
VALUES ($1, $2, $3, $4, $5)
ON CONFLICT (id) DO UPDATE SET text = EXCLUDED.text, region = EXCLUDED.region, type = EXCLUDED.type, data = EXCLUDED.data;
'''

async def migrate():
    if not DB_URL:
        print('DATABASE_URL or DATABASE_URL_UNPOOLED is not set in environment. Aborting migration.')
        return

    print('Connecting to', DB_URL.split('@')[-1][:80])
    conn = await asyncpg.connect(DB_URL)
    try:
        await conn.execute(CREATE_TABLE_SQL)
        print('Created table foods (or already exists)')

        if not os.path.exists(JSON_FILE):
            print(f'{JSON_FILE} not found. Nothing to populate.')
            return

        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            items = json.load(f)

        for item in items:
            iid = str(item.get('id'))
            text = item.get('text')
            region = item.get('region')
            typ = item.get('type')
            await conn.execute(INSERT_SQL, iid, text, region, typ, json.dumps(item))
        print(f'Inserted/updated {len(items)} rows into foods')
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(migrate())
