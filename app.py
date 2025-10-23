from flask import Flask, request, jsonify, send_from_directory
import asyncio
import os
import hashlib
import asyncpg

app = Flask(__name__, static_folder='frontend', static_url_path='')

# Import rag_query from rag_run. If rag_run cannot be imported because of
# missing environment variables or optional dependencies, provide a fallback
# async rag_query that returns a helpful message so the frontend can still run.
try:
    from rag_run import rag_query  # type: ignore
    from rag_run import migrate_data  # type: ignore
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


    def run_startup_migration():
        """Run migrate_data synchronously at startup if available."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            # migrate_data may be async and handle Upstash upserts
            loop.run_until_complete(migrate_data())
            print('Startup migration completed')
        except Exception as exc:
            print('Startup migration failed:', exc)



# Migration endpoints removed: use serverless endpoint at api/upsert-projects.py


@app.route('/')
def index():
    return send_from_directory('frontend', 'index.html')


@app.route('/admin.html')
def admin():
    return send_from_directory('frontend', 'admin.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json() or {}
    question = data.get('question', '')
    if not question:
        return jsonify({'error': 'question is required'}), 400

    # Run rag_query in asyncio loop
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        answer = loop.run_until_complete(rag_query(question))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    return jsonify({'answer': answer})


# Admin API endpoints
def hash_password(password: str) -> str:
    """Hash password using SHA-256."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


async def verify_password_async(password: str) -> bool:
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


@app.route('/api/admin', methods=['POST'])
def admin_verify():
    """Verify password for admin access."""
    try:
        body = request.get_json() or {}
        password = body.get('password', '')
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        is_valid = loop.run_until_complete(verify_password_async(password))
        
        if is_valid:
            return jsonify({'status': 'ok', 'authenticated': True})
        else:
            return jsonify({'status': 'error', 'message': 'Invalid password'}), 401
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/admin/records', methods=['POST'])
def admin_records():
    """List all records or create new record."""
    try:
        body = request.get_json() or {}
        password = body.get('password', '')
        
        # Verify password
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        is_valid = loop.run_until_complete(verify_password_async(password))
        
        if not is_valid:
            return jsonify({'status': 'error', 'message': 'Invalid password'}), 401
        
        DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('DATABASE_URL_UNPOOLED')
        if not DATABASE_URL:
            return jsonify({'status': 'error', 'message': 'Database not configured'}), 500
        
        # Check if this is a list request or create request
        if 'action' in body and body['action'] == 'list':
            # List all records
            async def list_records_async():
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
                    
                    return {'status': 'ok', 'records': records, 'count': len(records)}
                finally:
                    await conn.close()
            
            result = loop.run_until_complete(list_records_async())
            return jsonify(result)
        
        elif 'action' in body and body['action'] == 'create':
            # Create new record
            record = body.get('record', {})
            
            # Validate required fields
            if not record.get('id') or not record.get('type') or not record.get('title'):
                return jsonify({
                    'status': 'error', 
                    'message': 'Missing required fields: id, type, title'
                }), 400
            
            async def create_record_async():
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
                    
                    return {'status': 'ok', 'message': 'Record created successfully', 'id': record['id']}
                finally:
                    await conn.close()
            
            result = loop.run_until_complete(create_record_async())
            return jsonify(result)
        
        else:
            return jsonify({'status': 'error', 'message': 'Invalid action'}), 400
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/admin/upsert-all', methods=['POST'])
def admin_upsert_all():
    """Trigger upsert of all records to Upstash Vector."""
    try:
        body = request.get_json() or {}
        password = body.get('password', '')
        
        # Verify password
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        is_valid = loop.run_until_complete(verify_password_async(password))
        
        if not is_valid:
            return jsonify({'status': 'error', 'message': 'Invalid password'}), 401
        
        # Import here to avoid circular imports
        from migrate_utils import migrate_records_async
        
        stats = loop.run_until_complete(migrate_records_async())
        return jsonify({
            'status': 'ok',
            'message': 'Vector upsert completed',
            'stats': stats
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    # NOTE: migration is no longer run automatically on startup.
    # To embed projects into Upstash Vector, either run the script:
    #   python upsert_projects_to_vector.py
    # or call the HTTP endpoint POST /api/upsert-projects (see route below).

    port = int(os.environ.get('PORT', 7860))
    app.run(host='0.0.0.0', port=port, debug=True)
