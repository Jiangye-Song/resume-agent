from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import os
import asyncio
from dotenv import load_dotenv
import traceback
import time

load_dotenv()

app = FastAPI()

try:
    # rag_run provides async `rag_query` function
    from rag_run import rag_query  # type: ignore
except Exception as e:
    rag_query = None
    _import_error = str(e)


@app.post('/')
async def chat(request: Request):
    body = {}
    if request.headers.get('content-type', '').startswith('application/json'):
        body = await request.json()

    # Simple correlation id for logs
    log_id = str(int(time.time() * 1000))
    print(f"[chat] log_id={log_id} request_body={body}")

    question = body.get('question') if isinstance(body, dict) else None
    if not question:
        return JSONResponse({'error': 'question is required'})

    if rag_query is None:
        # Return JSON with error so frontend can parse it
        print(f"[chat][{log_id}] rag backend not available: {_import_error}")
        return JSONResponse({'error': f'RAG backend not available: {_import_error}', 'log_id': log_id})

    try:
        answer = await rag_query(question)
        return JSONResponse({'answer': answer})
    except Exception as exc:
        tb = traceback.format_exc()
        print(f"[chat][{log_id}] exception: {str(exc)}\n{tb}")
        # Return JSON with error detail and log_id to help debugging in Vercel logs
        return JSONResponse({'error': str(exc), 'log_id': log_id})


@app.get('/')
async def health(request: Request):
    """Simple health check so GET /api/chat returns JSON instead of HTML 404."""
    log_id = str(int(time.time() * 1000))
    print(f"[chat][health] log_id={log_id} ping")
    return JSONResponse({'status': 'ok', 'log_id': log_id})


@app.get('/{path_name:path}')
async def health_catch(request: Request, path_name: str):
    """Catch-all GET so requests forwarded as /api/chat or /api/chat/anything still return JSON."""
    log_id = str(int(time.time() * 1000))
    print(f"[chat][health] catch log_id={log_id} path={path_name}")
    return JSONResponse({'status': 'ok', 'log_id': log_id, 'path': path_name})


@app.post('/{path_name:path}')
async def chat_post_catch(request: Request, path_name: str):
    """Catch-all POST so requests forwarded as /api/chat or /api/chat/anything still invoke the chat handler."""
    # Reuse the main chat handler which expects a Request
    return await chat(request)
