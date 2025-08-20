from fastapi import FastAPI
from fastapi.responses import JSONResponse
import time

app = FastAPI()

@app.get('/')
async def hello():
    log_id = str(int(time.time() * 1000))
    print(f"[hello] log_id={log_id} ping")
    return JSONResponse({'status': 'ok', 'log_id': log_id})
