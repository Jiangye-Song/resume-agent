"""
Admin API endpoints for managing records.

Endpoints:
- POST /api/admin (root) - Verify password
- POST /api/admin/records - List all records (action='list') or Create new record (action='create')
- GET /api/admin/records/{record_id} - Get a single record by ID
- PUT /api/admin/records/{record_id} - Update an existing record
- DELETE /api/admin/records/{record_id} - Delete a record
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
    print(f"[admin] POST / called - path: {request.url.path}, full url: {request.url}")
    try:
        body = await request.json()
        password = body.get('password', '')
        
        if await verify_password(password):
            return JSONResponse({'status': 'ok', 'authenticated': True})
        else:
            return JSONResponse({'status': 'error', 'message': 'Invalid password'}, status_code=401)
    except Exception as e:
        print(f"[admin] Error in verify_auth: {e}")
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
                
                # Convert empty date strings to None
                start_date = record.get('start_date')
                if start_date == '':
                    start_date = None
                end_date = record.get('end_date')
                if end_date == '':
                    end_date = None
                
                await conn.execute('''
                    INSERT INTO records (id, type, title, summary, tags, detail_site, 
                                       additional_url, start_date, end_date, priority)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ''', 
                    record['id'],
                    record['type'],
                    record['title'],
                    record.get('summary'),
                    record.get('tags', []),
                    record.get('detail_site'),
                    additional_url,
                    start_date,
                    end_date,
                    record.get('priority', 3)
                )
                
                return JSONResponse({'status': 'ok', 'message': 'Record created successfully', 'id': record['id']})
            finally:
                await conn.close()
        except Exception as e:
            return JSONResponse({'status': 'error', 'message': str(e)}, status_code=500)
    
    else:
        return JSONResponse({'status': 'error', 'message': 'Invalid action'}, status_code=400)


@app.get('/records/{record_id}')
async def get_record(record_id: str, password: str = ''):
    """Get a single record by ID."""
    # Verify password
    if not await verify_password(password):
        return JSONResponse({'status': 'error', 'message': 'Invalid password'}, status_code=401)
    
    DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('DATABASE_URL_UNPOOLED')
    if not DATABASE_URL:
        return JSONResponse({'status': 'error', 'message': 'Database not configured'}, status_code=500)
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        try:
            row = await conn.fetchrow('''
                SELECT id, type, title, summary, tags, detail_site, additional_url,
                       start_date, end_date, priority
                FROM records
                WHERE id = $1
            ''', record_id)
            
            if not row:
                return JSONResponse({'status': 'error', 'message': 'Record not found'}, status_code=404)
            
            record = {
                'id': row['id'],
                'type': row['type'],
                'title': row['title'],
                'summary': row['summary'],
                'tags': list(row['tags']) if row['tags'] else [],
                'detail_site': row['detail_site'],
                'additional_url': row['additional_url'] if row['additional_url'] else [],
                'start_date': row['start_date'].isoformat() if row['start_date'] else None,
                'end_date': row['end_date'].isoformat() if row['end_date'] else None,
                'priority': row['priority']
            }
            
            return JSONResponse({'status': 'ok', 'record': record})
        finally:
            await conn.close()
    except Exception as e:
        return JSONResponse({'status': 'error', 'message': str(e)}, status_code=500)


@app.put('/records/{record_id}')
async def update_record(record_id: str, request: Request):
    """Update an existing record."""
    body = await request.json()
    password = body.get('password', '')
    
    # Verify password
    if not await verify_password(password):
        return JSONResponse({'status': 'error', 'message': 'Invalid password'}, status_code=401)
    
    DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('DATABASE_URL_UNPOOLED')
    if not DATABASE_URL:
        return JSONResponse({'status': 'error', 'message': 'Database not configured'}, status_code=500)
    
    record = body.get('record', {})
    
    # Validate required fields
    if not record.get('type') or not record.get('title'):
        return JSONResponse({
            'status': 'error', 
            'message': 'Missing required fields: type, title'
        }, status_code=400)
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        try:
            # Parse additional_url if it's a string
            additional_url = record.get('additional_url', [])
            if isinstance(additional_url, str):
                import json
                try:
                    additional_url = json.loads(additional_url)
                except:
                    additional_url = []
            
            await conn.execute('''
                UPDATE records
                SET type = $1, title = $2, summary = $3, tags = $4, detail_site = $5,
                    additional_url = $6, start_date = $7::date, end_date = $8::date, priority = $9
                WHERE id = $10
            ''', 
                record['type'],
                record['title'],
                record.get('summary'),
                record.get('tags', []),
                record.get('detail_site'),
                additional_url,
                record.get('start_date'),
                record.get('end_date'),
                record.get('priority', 3),
                record_id
            )
            
            return JSONResponse({'status': 'ok', 'message': 'Record updated successfully', 'id': record_id})
        finally:
            await conn.close()
    except Exception as e:
        return JSONResponse({'status': 'error', 'message': str(e)}, status_code=500)


@app.delete('/records/{record_id}')
async def delete_record(record_id: str, request: Request):
    """Delete a record."""
    body = await request.json()
    password = body.get('password', '')
    
    # Verify password
    if not await verify_password(password):
        return JSONResponse({'status': 'error', 'message': 'Invalid password'}, status_code=401)
    
    DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('DATABASE_URL_UNPOOLED')
    if not DATABASE_URL:
        return JSONResponse({'status': 'error', 'message': 'Database not configured'}, status_code=500)
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        try:
            await conn.execute('DELETE FROM records WHERE id = $1', record_id)
            return JSONResponse({'status': 'ok', 'message': 'Record deleted successfully', 'id': record_id})
        finally:
            await conn.close()
    except Exception as e:
        return JSONResponse({'status': 'error', 'message': str(e)}, status_code=500)


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


# Health check / debugging route
@app.get('/')
async def health_check():
    """Health check endpoint."""
    print(f"[admin] GET / health check called")
    return JSONResponse({'status': 'ok', 'service': 'admin'})


# Catch-all for debugging - must be last
@app.post('/{path_name:path}')
async def post_catch_all(request: Request, path_name: str):
    """Catch-all POST route for debugging."""
    print(f"[admin] POST catch-all: path={path_name}")
    
    # Handle /api/admin path (Vercel passes full path)
    if path_name == 'api/admin' or not path_name or path_name == '':
        return await verify_auth(request)
    
    # Handle /api/admin/records
    if path_name == 'api/admin/records':
        return await list_or_create_records(request)
    
    # Handle /api/admin/upsert-all
    if path_name == 'api/admin/upsert-all':
        return await upsert_all_records(request)
    
    return JSONResponse({'error': f'Unknown POST endpoint: {path_name}'}, status_code=404)


@app.get('/{path_name:path}')
async def get_catch_all(request: Request, path_name: str):
    """Catch-all GET route for debugging."""
    print(f"[admin] GET catch-all: path={path_name}")
    
    # Handle GET /api/admin/records/{id} with password query param
    if path_name.startswith('api/admin/records/'):
        record_id = path_name.split('/')[-1]
        password = request.query_params.get('password', '')
        
        # Verify password
        if not await verify_password(password):
            return JSONResponse({'status': 'error', 'message': 'Invalid password'}, status_code=401)
        
        # Get the record (extract logic from get_record endpoint)
        DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('DATABASE_URL_UNPOOLED')
        if not DATABASE_URL:
            return JSONResponse({'status': 'error', 'message': 'Database not configured'}, status_code=500)
        
        try:
            conn = await asyncpg.connect(DATABASE_URL)
            try:
                row = await conn.fetchrow('''
                    SELECT id, type, title, summary, tags, detail_site, additional_url,
                           start_date, end_date, priority
                    FROM records
                    WHERE id = $1
                ''', record_id)
                
                if not row:
                    return JSONResponse({'status': 'error', 'message': 'Record not found'}, status_code=404)
                
                record = {
                    'id': row['id'],
                    'type': row['type'],
                    'title': row['title'],
                    'summary': row['summary'],
                    'tags': list(row['tags']) if row['tags'] else [],
                    'detail_site': row['detail_site'],
                    'additional_url': row['additional_url'] if row['additional_url'] else [],
                    'start_date': row['start_date'].isoformat() if row['start_date'] else None,
                    'end_date': row['end_date'].isoformat() if row['end_date'] else None,
                    'priority': row['priority']
                }
                
                return JSONResponse({'status': 'ok', 'record': record})
            finally:
                await conn.close()
        except Exception as e:
            return JSONResponse({'status': 'error', 'message': str(e)}, status_code=500)
    
    return JSONResponse({'error': f'Unknown GET endpoint: {path_name}'}, status_code=404)


@app.put('/{path_name:path}')
async def put_catch_all(request: Request, path_name: str):
    """Catch-all PUT route."""
    print(f"[admin] PUT catch-all: path={path_name}")
    
    # Handle PUT /api/admin/records/{id}
    if path_name.startswith('api/admin/records/'):
        record_id = path_name.split('/')[-1]
        body = await request.json()
        password = body.get('password', '')
        
        # Verify password
        if not await verify_password(password):
            return JSONResponse({'status': 'error', 'message': 'Invalid password'}, status_code=401)
        
        DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('DATABASE_URL_UNPOOLED')
        if not DATABASE_URL:
            return JSONResponse({'status': 'error', 'message': 'Database not configured'}, status_code=500)
        
        record = body.get('record', {})
        
        # Validate required fields
        if not record.get('type') or not record.get('title'):
            return JSONResponse({
                'status': 'error', 
                'message': 'Missing required fields: type, title'
            }, status_code=400)
        
        try:
            conn = await asyncpg.connect(DATABASE_URL)
            try:
                # Parse additional_url if it's a string
                additional_url = record.get('additional_url', [])
                if isinstance(additional_url, str):
                    import json
                    try:
                        additional_url = json.loads(additional_url)
                    except:
                        additional_url = []
                
                # Convert empty date strings to None
                start_date = record.get('start_date')
                if start_date == '':
                    start_date = None
                end_date = record.get('end_date')
                if end_date == '':
                    end_date = None
                
                await conn.execute('''
                    UPDATE records
                    SET type = $1, title = $2, summary = $3, tags = $4, detail_site = $5,
                        additional_url = $6, start_date = $7, end_date = $8, priority = $9
                    WHERE id = $10
                ''', 
                    record['type'],
                    record['title'],
                    record.get('summary'),
                    record.get('tags', []),
                    record.get('detail_site'),
                    additional_url,
                    start_date,
                    end_date,
                    record.get('priority', 3),
                    record_id
                )
                
                return JSONResponse({'status': 'ok', 'message': 'Record updated successfully', 'id': record_id})
            finally:
                await conn.close()
        except Exception as e:
            return JSONResponse({'status': 'error', 'message': str(e)}, status_code=500)
    
    return JSONResponse({'error': f'Unknown PUT endpoint: {path_name}'}, status_code=404)


@app.delete('/{path_name:path}')
async def delete_catch_all(request: Request, path_name: str):
    """Catch-all DELETE route."""
    print(f"[admin] DELETE catch-all: path={path_name}")
    
    # Handle DELETE /api/admin/records/{id}
    if path_name.startswith('api/admin/records/'):
        record_id = path_name.split('/')[-1]
        body = await request.json()
        password = body.get('password', '')
        
        # Verify password
        if not await verify_password(password):
            return JSONResponse({'status': 'error', 'message': 'Invalid password'}, status_code=401)
        
        DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('DATABASE_URL_UNPOOLED')
        if not DATABASE_URL:
            return JSONResponse({'status': 'error', 'message': 'Database not configured'}, status_code=500)
        
        try:
            conn = await asyncpg.connect(DATABASE_URL)
            try:
                await conn.execute('DELETE FROM records WHERE id = $1', record_id)
                return JSONResponse({'status': 'ok', 'message': 'Record deleted successfully', 'id': record_id})
            finally:
                await conn.close()
        except Exception as e:
            return JSONResponse({'status': 'error', 'message': str(e)}, status_code=500)
    
    return JSONResponse({'error': f'Unknown DELETE endpoint: {path_name}'}, status_code=404)
