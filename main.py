from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os
import hashlib
import asyncpg
from datetime import date, datetime

# Database connection pool
db_pool = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage database connection pool lifecycle."""
    global db_pool
    DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('DATABASE_URL_UNPOOLED')
    if DATABASE_URL:
        try:
            db_pool = await asyncpg.create_pool(
                DATABASE_URL,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            print("Database connection pool initialized")
        except Exception as e:
            print(f"Failed to create database pool: {e}")
    
    yield
    
    if db_pool:
        await db_pool.close()
        print("Database connection pool closed")


app = FastAPI(lifespan=lifespan)

# Import rag_query from rag_run with fallback
try:
    from rag_run import rag_query  # type: ignore
except Exception as e:
    async def rag_query(question: str) -> str:
        return (
            "RAG backend is not available.\n"
            "Failed to import rag_run or initialize vector/LLM clients.\n"
            f"Error: {str(e)}\n\n"
            "To enable the full backend, set the required environment variables:"
            " UPSTASH_VECTOR_REST_URL, UPSTASH_VECTOR_REST_TOKEN, GROQ_API_KEY, VECTOR_DB_TYPE=upstash, LLM_PROVIDER=groq\n"
            "Then install dependencies from requirements.txt and restart the server."
        )


# Utility functions
def hash_password(password: str) -> str:
    """Hash password using SHA-256."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def parse_date(date_str):
    """Parse date string to date object, return None if empty or invalid."""
    if not date_str or date_str.strip() == '':
        return None
    try:
        if isinstance(date_str, date):
            return date_str
        # Parse YYYY-MM-DD format
        from datetime import datetime
        return datetime.strptime(date_str.strip(), '%Y-%m-%d').date()
    except (ValueError, AttributeError):
        return None


async def verify_password(password: str) -> bool:
    """Verify password against stored hash in config table."""
    global db_pool
    if not db_pool:
        return False
    
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT value FROM config WHERE key = 'panel_passcode'"
            )
            if not row:
                return False
            
            stored_hash = row['value']
            input_hash = hash_password(password)
            return stored_hash == input_hash
    except Exception as e:
        print(f"Password verification error: {e}")
        return False


# Chat endpoint
@app.post('/api/chat')
async def chat(request: Request):
    """Chat endpoint using RAG."""
    body = await request.json()
    question = body.get('question', '')
    
    if not question:
        return JSONResponse({'error': 'question is required'}, status_code=400)
    
    try:
        answer = await rag_query(question)
        return JSONResponse({'answer': answer})
    except Exception as e:
        return JSONResponse({'error': str(e)}, status_code=500)


# Admin endpoints
@app.post('/api/admin')
async def admin_verify(request: Request):
    """Verify password for admin access."""
    body = await request.json()
    password = body.get('password', '')
    
    if await verify_password(password):
        return JSONResponse({'status': 'ok', 'authenticated': True})
    else:
        return JSONResponse({'status': 'error', 'message': 'Invalid password'}, status_code=401)


@app.post('/api/admin/records')
async def list_or_create_records(request: Request):
    """List all records or create new record."""
    body = await request.json()
    password = body.get('password', '')
    
    if not await verify_password(password):
        return JSONResponse({'status': 'error', 'message': 'Invalid password'}, status_code=401)
    
    DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('DATABASE_URL_UNPOOLED')
    if not DATABASE_URL:
        return JSONResponse({'status': 'error', 'message': 'Database not configured'}, status_code=500)
    
    action = body.get('action', '')
    
    if action == 'list':
        # List all records
        try:
            async with db_pool.acquire() as conn:
                # Only select columns needed for the table display (not summary, detail_site, additional_url, facts)
                rows = await conn.fetch('''
                    SELECT id, type, title, tags, start_date, end_date, priority
                    FROM records
                    ORDER BY priority DESC, type, id
                ''')
                
                records = []
                for r in rows:
                    records.append({
                        'id': r['id'],
                        'type': r['type'],
                        'title': r['title'],
                        'tags': list(r['tags']) if r['tags'] else [],
                        'start_date': r['start_date'].isoformat() if r['start_date'] else None,
                        'end_date': r['end_date'].isoformat() if r['end_date'] else None,
                        'priority': r['priority']
                    })
                
                return JSONResponse({'status': 'ok', 'records': records, 'count': len(records)})
        except Exception as e:
            return JSONResponse({'status': 'error', 'message': str(e)}, status_code=500)
    
    elif action == 'create':
        # Create new record
        record = body.get('record', {})
        
        if not record.get('id') or not record.get('type') or not record.get('title'):
            return JSONResponse({
                'status': 'error', 
                'message': 'Missing required fields: id, type, title'
            }, status_code=400)
        
        try:
            async with db_pool.acquire() as conn:
                # Parse additional_url if it's a string
                additional_url = record.get('additional_url', [])
                if isinstance(additional_url, str):
                    import json
                    try:
                        additional_url = json.loads(additional_url)
                    except:
                        additional_url = []
                
                # Process facts field
                facts = record.get('facts', [])
                print(f"[FastAPI] CREATE - Raw facts: {repr(facts)}")
                if isinstance(facts, str):
                    facts = [line.strip() for line in facts.split('\n') if line.strip()]
                    print(f"[FastAPI] CREATE - Processed facts: {facts}")
                elif not isinstance(facts, list):
                    facts = []
                
                await conn.execute('''
                    INSERT INTO records (id, type, title, summary, tags, detail_site, 
                                       additional_url, start_date, end_date, priority, facts)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ''', 
                    record['id'],
                    record['type'],
                    record['title'],
                    record.get('summary'),
                    record.get('tags', []),
                    record.get('detail_site'),
                    additional_url,
                    parse_date(record.get('start_date')),
                    parse_date(record.get('end_date')),
                    record.get('priority', 3),
                    facts
                )
                
                return JSONResponse({'status': 'ok', 'message': 'Record created successfully', 'id': record['id']})
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"[FastAPI] Error creating record: {e}")
            print(f"[FastAPI] Traceback: {error_detail}")
            return JSONResponse({'status': 'error', 'message': str(e)}, status_code=500)
    
    else:
        return JSONResponse({'status': 'error', 'message': 'Invalid action'}, status_code=400)


@app.get('/api/admin/records/{record_id}')
async def get_record(record_id: str, password: str = ''):
    """Get a single record by ID."""
    if not await verify_password(password):
        return JSONResponse({'status': 'error', 'message': 'Invalid password'}, status_code=401)
    
    DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('DATABASE_URL_UNPOOLED')
    if not DATABASE_URL:
        return JSONResponse({'status': 'error', 'message': 'Database not configured'}, status_code=500)
    
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow('''
                SELECT id, type, title, summary, tags, detail_site, additional_url,
                       start_date, end_date, priority, facts
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
                'priority': row['priority'],
                'facts': list(row['facts']) if row['facts'] else []
            }
            
            return JSONResponse({'status': 'ok', 'record': record})
    except Exception as e:
        return JSONResponse({'status': 'error', 'message': str(e)}, status_code=500)


@app.put('/api/admin/records/{record_id}')
async def update_record(record_id: str, request: Request):
    """Update an existing record."""
    body = await request.json()
    password = body.get('password', '')
    
    if not await verify_password(password):
        return JSONResponse({'status': 'error', 'message': 'Invalid password'}, status_code=401)
    
    DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('DATABASE_URL_UNPOOLED')
    if not DATABASE_URL:
        return JSONResponse({'status': 'error', 'message': 'Database not configured'}, status_code=500)
    
    record = body.get('record', {})
    
    if not record.get('type') or not record.get('title'):
        return JSONResponse({
            'status': 'error', 
            'message': 'Missing required fields: type, title'
        }, status_code=400)
    
    try:
        async with db_pool.acquire() as conn:
            # Parse additional_url if it's a string
            additional_url = record.get('additional_url', [])
            if isinstance(additional_url, str):
                import json
                try:
                    additional_url = json.loads(additional_url)
                except:
                    additional_url = []
            
            # Process facts field
            facts = record.get('facts', [])
            print(f"[FastAPI] UPDATE - Raw facts: {repr(facts)}")
            if isinstance(facts, str):
                facts = [line.strip() for line in facts.split('\n') if line.strip()]
                print(f"[FastAPI] UPDATE - Processed facts: {facts}")
            elif not isinstance(facts, list):
                facts = []
            print(f"[FastAPI] UPDATE - Final facts to save: {facts}")
            
            await conn.execute('''
                UPDATE records
                SET type = $1, title = $2, summary = $3, tags = $4, detail_site = $5,
                    additional_url = $6, start_date = $7, end_date = $8, priority = $9, facts = $10
                WHERE id = $11
            ''', 
                record['type'],
                record['title'],
                record.get('summary'),
                record.get('tags', []),
                record.get('detail_site'),
                additional_url,
                parse_date(record.get('start_date')),
                parse_date(record.get('end_date')),
                record.get('priority', 3),
                facts,
                record_id
            )
            
            return JSONResponse({'status': 'ok', 'message': 'Record updated successfully', 'id': record_id})
    except Exception as e:
        return JSONResponse({'status': 'error', 'message': str(e)}, status_code=500)


@app.delete('/api/admin/records/{record_id}')
async def delete_record(record_id: str, request: Request):
    """Delete a record."""
    body = await request.json()
    password = body.get('password', '')
    
    if not await verify_password(password):
        return JSONResponse({'status': 'error', 'message': 'Invalid password'}, status_code=401)
    
    DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('DATABASE_URL_UNPOOLED')
    if not DATABASE_URL:
        return JSONResponse({'status': 'error', 'message': 'Database not configured'}, status_code=500)
    
    try:
        async with db_pool.acquire() as conn:
            await conn.execute('DELETE FROM records WHERE id = $1', record_id)
            return JSONResponse({'status': 'ok', 'message': 'Record deleted successfully', 'id': record_id})
    except Exception as e:
        return JSONResponse({'status': 'error', 'message': str(e)}, status_code=500)


@app.post('/api/admin/upsert-all')
async def upsert_all_records(request: Request):
    """Trigger upsert of all records to Upstash Vector."""
    body = await request.json()
    password = body.get('password', '')
    
    if not await verify_password(password):
        return JSONResponse({'status': 'error', 'message': 'Invalid password'}, status_code=401)
    
    try:
        from migrate_utils import migrate_records_async
        stats = await migrate_records_async()
        return JSONResponse({
            'status': 'ok',
            'message': 'Vector upsert completed',
            'stats': stats
        })
    except Exception as e:
        return JSONResponse({'status': 'error', 'message': str(e)}, status_code=500)


@app.post('/api/admin/generate-facts')
async def generate_facts(request: Request):
    """Generate a list of facts from a summary using LLM."""
    body = await request.json()
    password = body.get('password', '')
    summary = body.get('summary', '')
    
    if not await verify_password(password):
        return JSONResponse({'status': 'error', 'message': 'Invalid password'}, status_code=401)
    
    if not summary:
        return JSONResponse({'status': 'error', 'message': 'Summary is required'}, status_code=400)
    
    try:
        # Import Groq client
        from groq import Groq
        GROQ_API_KEY = os.getenv("GROQ_API_KEY")
        
        if not GROQ_API_KEY:
            return JSONResponse({'status': 'error', 'message': 'LLM API not configured'}, status_code=500)
        
        groq_client = Groq(api_key=GROQ_API_KEY)
        
        # Create prompt for facts generation
        prompt = f"""Convert the following summary into a concise list of factual bullet points. 
Extract only the key facts, achievements, and technical details. 
Each fact should be one line, clear and specific.
Return only the bullet points, one per line, without numbering or bullet symbols.

Summary:
{summary}

Facts (one per line):"""
        
        # Call LLM
        response = groq_client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            messages=[
                {"role": "system", "content": "You are a helpful assistant that extracts key facts from text summaries. Be concise and specific."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        # Extract facts from response
        facts_text = response.choices[0].message.content.strip()
        
        # Split into lines and clean up
        facts = [line.strip() for line in facts_text.split('\n') if line.strip() and not line.strip().startswith('#')]
        
        # Remove common bullet point symbols if present
        facts = [fact.lstrip('•-*→▸▹►‣⁃').strip() for fact in facts]
        
        return JSONResponse({
            'status': 'ok',
            'facts': facts
        })
    except Exception as e:
        import traceback
        print(f"Error generating facts: {e}")
        print(traceback.format_exc())
        return JSONResponse({'status': 'error', 'message': str(e)}, status_code=500)


# Mount static files first (must be before specific routes)
app.mount('/frontend', StaticFiles(directory='frontend'), name='frontend')

# Serve static files (frontend)
@app.get('/')
async def serve_index():
    return FileResponse('frontend/index.html')


@app.get('/admin.html')
async def serve_admin():
    return FileResponse('frontend/admin.html')


@app.get('/style.css')
async def serve_style():
    return FileResponse('frontend/style.css')


@app.get('/script.js')
async def serve_script():
    return FileResponse('frontend/script.js')


if __name__ == '__main__':
    import uvicorn
    port = int(os.environ.get('PORT', 7860))
    uvicorn.run(app, host='0.0.0.0', port=port)
