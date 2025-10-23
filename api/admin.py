"""
Admin API endpoints for managing records.

Endpoints:
- POST /api/admin (root) - Verify password
- GET /api/admin/records - List all records
- POST /api/admin/records - Create new record
- POST /api/admin/upsert-all - Trigger upsert of all records to vector DB
"""
import os
import asyncio
import asyncpg
import hashlib
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from migrate_utils import migrate_records_async

load_dotenv()

app = FastAPI()


def hash_password(password: str) -> str:
    """Hash password using SHA-256."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


async def verify_password(password: str) -> bool:
    """Verify password against stored hash in config table."""
    DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('DATABASE_URL_UNPOOLED')
    if not DATABASE_URL:
        return False
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        try:
            row = await conn.fetchrow(
                "SELECT value FROM config WHERE key = 'panel_passcode'"
            )
            if not row:
                return False
            
            stored_hash = row['value']
            input_hash = hash_password(password)
            return stored_hash == input_hash
        finally:
            await conn.close()
    except Exception as e:
        print(f"Password verification error: {e}")
        return False


@app.post('/')
async def verify_auth(request: Request):
    """Verify password for admin access."""
    try:
        body = await request.json()
        password = body.get('password', '')
        
        if await verify_password(password):
            return JSONResponse({'status': 'ok', 'authenticated': True})
        else:
            return JSONResponse({'status': 'error', 'message': 'Invalid password'}, status_code=401)
    except Exception as e:
        return JSONResponse({'status': 'error', 'message': str(e)}, status_code=500)


@app.post('/records')
async def list_or_create_records(request: Request):
    """List all records or create new record."""
    body = await request.json()
    password = body.get('password', '')
    
    # Verify password
    if not await verify_password(password):
        return JSONResponse({'status': 'error', 'message': 'Invalid password'}, status_code=401)
    
    DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('DATABASE_URL_UNPOOLED')
    if not DATABASE_URL:
        return JSONResponse({'status': 'error', 'message': 'Database not configured'}, status_code=500)
    
    # Check if this is a list request or create request
    if 'action' in body and body['action'] == 'list':
        # List all records
        try:
            conn = await asyncpg.connect(DATABASE_URL)
            try:
                rows = await conn.fetch('''
                    SELECT id, type, title, summary, tags, detail_site, additional_url,
                           start_date, end_date, priority
                    FROM records
                    ORDER BY priority DESC, type, id
                ''')
                
                records = []
                for r in rows:
                    records.append({
                        'id': r['id'],
                        'type': r['type'],
                        'title': r['title'],
                        'summary': r['summary'],
                        'tags': list(r['tags']) if r['tags'] else [],
                        'detail_site': r['detail_site'],
                        'additional_url': r['additional_url'] if r['additional_url'] else [],
                        'start_date': r['start_date'].isoformat() if r['start_date'] else None,
                        'end_date': r['end_date'].isoformat() if r['end_date'] else None,
                        'priority': r['priority']
                    })
                
                return JSONResponse({'status': 'ok', 'records': records, 'count': len(records)})
            finally:
                await conn.close()
        except Exception as e:
            return JSONResponse({'status': 'error', 'message': str(e)}, status_code=500)
    
    elif 'action' in body and body['action'] == 'create':
        # Create new record
        record = body.get('record', {})
        
        # Validate required fields
        if not record.get('id') or not record.get('type') or not record.get('title'):
            return JSONResponse({
                'status': 'error', 
                'message': 'Missing required fields: id, type, title'
            }, status_code=400)
        
        try:
            conn = await asyncpg.connect(DATABASE_URL)
            try:
                # Parse additional_url if it's a string
                additional_url = record.get('additional_url', [])
                if isinstance(additional_url, str):
                    # Try to parse JSON array
                    import json
                    try:
                        additional_url = json.loads(additional_url)
                    except:
                        additional_url = []
                
                await conn.execute('''
                    INSERT INTO records (id, type, title, summary, tags, detail_site, 
                                       additional_url, start_date, end_date, priority)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8::date, $9::date, $10)
                ''', 
                    record['id'],
                    record['type'],
                    record['title'],
                    record.get('summary'),
                    record.get('tags', []),
                    record.get('detail_site'),
                    additional_url,
                    record.get('start_date'),
                    record.get('end_date'),
                    record.get('priority', 3)
                )
                
                return JSONResponse({'status': 'ok', 'message': 'Record created successfully', 'id': record['id']})
            finally:
                await conn.close()
        except Exception as e:
            return JSONResponse({'status': 'error', 'message': str(e)}, status_code=500)
    
    else:
        return JSONResponse({'status': 'error', 'message': 'Invalid action'}, status_code=400)


@app.post('/upsert-all')
async def upsert_all_records(request: Request):
    """Trigger upsert of all records to Upstash Vector."""
    body = await request.json()
    password = body.get('password', '')
    
    # Verify password
    if not await verify_password(password):
        return JSONResponse({'status': 'error', 'message': 'Invalid password'}, status_code=401)
    
    try:
        stats = await migrate_records_async()
        return JSONResponse({
            'status': 'ok',
            'message': 'Vector upsert completed',
            'stats': stats
        })
    except Exception as e:
        return JSONResponse({'status': 'error', 'message': str(e)}, status_code=500)
