"""
Seed script to create a `projects` table and insert mock portfolio projects for local testing.

Usage:
    python db_seed_projects.py

It reads DATABASE_URL or DATABASE_URL_UNPOOLED from environment.
"""
import os
import json
import asyncio
import asyncpg

DB_URL = os.environ.get('DATABASE_URL') or os.environ.get('DATABASE_URL_UNPOOLED')

CREATE_TABLE_SQL = '''
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    title TEXT,
    summary TEXT,
    tags TEXT[],
    url TEXT,
    data JSONB
);
'''

INSERT_SQL = '''
INSERT INTO projects (id, title, summary, tags, url, data)
VALUES ($1, $2, $3, $4, $5, $6)
ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, summary = EXCLUDED.summary, tags = EXCLUDED.tags, url = EXCLUDED.url, data = EXCLUDED.data;
'''

MOCK_PROJECTS = [
    {
        "id": "proj-1",
        "title": "Personal Portfolio Website",
        "summary": "A responsive portfolio site built with React and Tailwind to showcase projects and blog posts.",
        "tags": ["react", "tailwind", "frontend"],
        "url": "https://example.com/portfolio",
        "details": {
            "role": "Full-stack developer",
            "duration": "3 months",
            "highlights": [
                "Responsive UI",
                "CMS integration for blog posts",
                "Deployed via Vercel"
            ]
        }
    },
    {
        "id": "proj-2",
        "title": "Resume AI Assistant",
        "summary": "An agent that reads a user's resume and answers job- and skills-related questions using RAG.",
        "tags": ["python", "rasa", "llm"],
        "url": "https://example.com/resume-agent",
        "details": {
            "role": "Research Engineer",
            "duration": "2 months",
            "highlights": ["RAG pipeline", "Vector DB integration", "Deployment-ready Dockerfile"]
        }
    },
    {
        "id": "proj-3",
        "title": "Expense Tracker API",
        "summary": "A RESTful API for tracking expenses built with FastAPI and Postgres.",
        "tags": ["fastapi", "postgres", "backend"],
        "url": "https://example.com/expense-api",
        "details": {
            "role": "Backend Developer",
            "duration": "1.5 months",
            "highlights": ["JWT auth", "CRUD endpoints", "OpenAPI docs"]
        }
    }
]


async def seed():
    if not DB_URL:
        print('DATABASE_URL or DATABASE_URL_UNPOOLED not set. Aborting seeding.')
        return

    print('Connecting to', DB_URL.split('@')[-1][:80])
    conn = await asyncpg.connect(DB_URL)
    try:
        await conn.execute(CREATE_TABLE_SQL)
        print('Ensured projects table exists')

        for p in MOCK_PROJECTS:
            await conn.execute(INSERT_SQL, p['id'], p['title'], p['summary'], p['tags'], p['url'], json.dumps(p))
        print(f'Seeded {len(MOCK_PROJECTS)} mock projects')
    finally:
        await conn.close()


if __name__ == '__main__':
    asyncio.run(seed())
