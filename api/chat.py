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
        raise HTTPException(status_code=400, detail='question is required')

    if rag_query is None:
        # Provide helpful error so frontend can show a friendly message
        raise HTTPException(status_code=500, detail=f'RAG backend not available: {_import_error}')

    try:
        answer = await rag_query(question)
        return JSONResponse({'answer': answer})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
