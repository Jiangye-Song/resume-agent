from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import os
import asyncio
from dotenv import load_dotenv

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

    question = body.get('question') if isinstance(body, dict) else None
    if not question:
        return JSONResponse({'error': 'question is required'})

    if rag_query is None:
        # Return JSON with error so frontend can parse it
        return JSONResponse({'error': f'RAG backend not available: {_import_error}'})

    try:
        answer = await rag_query(question)
        return JSONResponse({'answer': answer})
    except Exception as exc:
        # Return JSON with error detail to avoid HTML error pages
        return JSONResponse({'error': str(exc)})
