from fastapi import FastAPI
from fastapi.responses import JSONResponse
import time

app = FastAPI()

@app.get('/')
async def hello():
    log_id = str(int(time.time() * 1000))
    print(f"[hello] log_id={log_id} ping")
    return JSONResponse({'status': 'ok', 'log_id': log_id})


@app.get('/{path_name:path}')
async def hello_catch(path_name: str):
    # Catch-all so requests forwarded as /api/hello or /api/hello/whatever still succeed
    log_id = str(int(time.time() * 1000))
    print(f"[hello] catch log_id={log_id} path={path_name}")
    return JSONResponse({'status': 'ok', 'log_id': log_id, 'path': path_name})
