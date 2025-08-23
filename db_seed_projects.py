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
    data JSONB,
    start_date DATE,
    end_date DATE,
    priority INTEGER DEFAULT 3
);
'''

INSERT_SQL = '''
INSERT INTO projects (id, title, summary, tags, url, data, start_date, end_date, priority)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
ON CONFLICT (id) DO UPDATE SET 
    title = EXCLUDED.title, 
    summary = EXCLUDED.summary, 
    tags = EXCLUDED.tags, 
    url = EXCLUDED.url, 
    data = EXCLUDED.data,
    start_date = EXCLUDED.start_date,
    end_date = EXCLUDED.end_date,
    priority = EXCLUDED.priority;
'''

MOCK_PROJECTS = [
    {
        "id": "proj-1",
        "title": "Personal Portfolio Website",
        "summary": "A responsive portfolio site built with React and Tailwind to showcase projects and blog posts.",
        "tags": ["react", "tailwind", "frontend"],
        "url": "https://example.com/portfolio",
        "start_date": "2024-01-15",
        "end_date": "2024-04-15",
        "priority": 2,  # 中等优先级
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
        "start_date": "2025-08-01",
        "end_date": None,  # Ongoing project
        "priority": 3,  # 最高优先级
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
        "start_date": "2024-06-01",
        "end_date": "2024-07-15",
        "priority": 1,  # 低优先级
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
            # Convert date strings to date objects (None stays None)
            start_date = p['start_date'] if p['start_date'] else None
            end_date = p['end_date'] if p['end_date'] else None
            
            await conn.execute(
                INSERT_SQL, 
                p['id'], 
                p['title'], 
                p['summary'], 
                p['tags'], 
                p['url'], 
                json.dumps(p),
                start_date,
                end_date,
                p.get('priority', 3)  # Default to 3 if not specified
            )
        print(f'Seeded {len(MOCK_PROJECTS)} mock projects')
    finally:
        await conn.close()


if __name__ == '__main__':
    asyncio.run(seed())
