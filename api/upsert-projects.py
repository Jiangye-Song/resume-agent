from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import os
import asyncio
from migrate_utils import migrate_projects_async
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()


@app.post('/')
async def upsert_projects(request: Request):
    body = await request.json() if request.headers.get('content-type') == 'application/json' else {}
    key_required = os.getenv('MIGRATION_KEY')
    if key_required:
        if not isinstance(body, dict) or body.get('key') != key_required:
            raise HTTPException(status_code=403, detail='invalid key')

    try:
        stats = await migrate_projects_async()
        return JSONResponse({'status': 'completed', 'stats': stats})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
