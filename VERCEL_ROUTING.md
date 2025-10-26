# Vercel Routing for Python Web Frameworks

This document explains how Vercel handles routing for Python web applications, specifically FastAPI and Flask apps.

## Overview

When you deploy a Python web application to Vercel, each Python file in the `api/` directory becomes a **serverless function**. Vercel's routing system maps incoming HTTP requests to these functions.

## Key Concepts

### 1. Serverless Functions

Each `.py` file in the `api/` folder is treated as a separate serverless function:
- `api/admin.py` → handles requests routed to it
- `api/chat.py` → handles requests routed to it
- `api/hello.py` → handles requests routed to it

### 2. Path Preservation

**Critical Understanding**: When Vercel routes a request to a Python file, it passes the **full original path** to your application, not just the remaining path segments.

#### Example:
```
Incoming request: POST /api/admin
Vercel routing:   { "src": "/api/admin", "dest": "/api/admin.py" }
Path seen by app: "api/admin" (or "/api/admin")
```

The FastAPI/Flask app receives `api/admin`, **NOT** `/` or an empty path.

### 3. vercel.json Configuration

The `vercel.json` file has two main sections:

#### Builds
Tells Vercel how to build each part of your project:

```json
{
  "builds": [
    { "src": "api/admin.py", "use": "@vercel/python" },
    { "src": "api/chat.py", "use": "@vercel/python" },
    { "src": "frontend/**", "use": "@vercel/static" }
  ]
}
```

- `@vercel/python` - Handles Python serverless functions (FastAPI/Flask/ASGI/WSGI)
- `@vercel/static` - Serves static files (HTML, CSS, JS, images)

#### Routes
Maps incoming request paths to their destination:

```json
{
  "routes": [
    { "src": "/api/admin/records/([^/]+)", "dest": "/api/admin.py" },
    { "src": "/api/admin/records", "dest": "/api/admin.py" },
    { "src": "/api/admin", "dest": "/api/admin.py" },
    { "src": "/", "dest": "/frontend/index.html" }
  ]
}
```

**Route Order Matters!** More specific routes should come first.

## FastAPI on Vercel

### Native Support

Vercel's `@vercel/python` runtime **natively supports** FastAPI (and other ASGI apps). You don't need Mangum or any adapter.

### Example Structure

```python
from fastapi import FastAPI, Request

app = FastAPI()

@app.post('/{path_name:path}')
async def handler(request: Request, path_name: str):
    print(f"Received path: {path_name}")
    
    # Handle full path from Vercel
    if path_name == 'api/admin':
        # Handle login
        pass
    elif path_name == 'api/admin/records':
        # Handle records
        pass
```

### Key Points

1. **No special handler needed** - Just define `app = FastAPI()`
2. **Use catch-all routes** - `/{path_name:path}` captures all paths
3. **Match full paths** - Check for `api/admin`, not just `/admin`
4. **Route detection** - Use `if` statements to route to different handlers

## Flask on Vercel

### Similar Approach

Flask works similarly, but with Flask routing syntax:

```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/<path:path_name>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def catch_all(path_name=''):
    print(f"Received path: {path_name}")
    
    if path_name == 'api/admin':
        # Handle login
        pass
    elif path_name == 'api/admin/records':
        # Handle records
        pass
```

## Common Patterns

### Pattern 1: Explicit Routes (Preferred for Simple APIs)

```json
{
  "routes": [
    { "src": "/api/users", "dest": "/api/users.py" },
    { "src": "/api/posts", "dest": "/api/posts.py" }
  ]
}
```

Each endpoint has its own file. Simple and clean.

### Pattern 2: Catch-All Routes (Preferred for Complex APIs)

```json
{
  "routes": [
    { "src": "/api/admin/(.*)", "dest": "/api/admin.py" },
    { "src": "/api/admin", "dest": "/api/admin.py" }
  ]
}
```

One file handles multiple related endpoints. More flexible.

### Pattern 3: Regex Routes

```json
{
  "routes": [
    { "src": "/api/users/([^/]+)", "dest": "/api/users.py" },
    { "src": "/api/users", "dest": "/api/users.py" }
  ]
}
```

Matches patterns like `/api/users/123` and `/api/users`.

## Debugging Tips

### 1. Add Logging

```python
@app.post('/{path_name:path}')
async def handler(request: Request, path_name: str):
    print(f"[DEBUG] Path: {path_name}")
    print(f"[DEBUG] Method: {request.method}")
    print(f"[DEBUG] Full URL: {request.url}")
```

Check Vercel function logs to see what paths your app receives.

### 2. Test Locally

Run your app locally to understand routing:

```bash
uvicorn api.admin:app --reload
# Visit http://localhost:8000/api/admin
```

Locally, you'll hit `/api/admin` directly. On Vercel, the same path is passed through.

### 3. Return Diagnostic Info

```python
@app.get('/{path_name:path}')
async def debug(path_name: str):
    return JSONResponse({
        'path': path_name,
        'message': 'Debugging route'
    })
```

## Common Pitfalls

### ❌ Pitfall 1: Expecting Path Stripping

```python
# WRONG - Expecting Vercel to strip /api/admin prefix
@app.post('/')
async def login(request: Request):
    # This WON'T match /api/admin
    pass
```

**Solution**: Use catch-all routes and check the full path.

### ❌ Pitfall 2: Using Mangum

```python
# UNNECESSARY - Vercel supports FastAPI natively
from mangum import Mangum
handler = Mangum(app)
```

**Solution**: Remove Mangum. Just use `app = FastAPI()`.

### ❌ Pitfall 3: Wrong Route Order

```json
{
  "routes": [
    { "src": "/(.*)", "dest": "/frontend/$1" },  // Too broad!
    { "src": "/api/admin", "dest": "/api/admin.py" }  // Never reached
  ]
}
```

**Solution**: Put specific routes first, catch-all routes last.

### ❌ Pitfall 4: Forgetting Static Build

```json
{
  "builds": [
    { "src": "api/**/*.py", "use": "@vercel/python" }
    // Missing: { "src": "frontend/**", "use": "@vercel/static" }
  ]
}
```

**Solution**: Always include static file builds for frontend assets.

## Best Practices

### ✅ 1. Explicit Builds

List each Python file explicitly:

```json
{
  "builds": [
    { "src": "api/admin.py", "use": "@vercel/python" },
    { "src": "api/chat.py", "use": "@vercel/python" }
  ]
}
```

More reliable than wildcards during deployment.

### ✅ 2. Specific Routes First

```json
{
  "routes": [
    { "src": "/api/admin/upsert-all", "dest": "/api/admin.py" },
    { "src": "/api/admin/records/([^/]+)", "dest": "/api/admin.py" },
    { "src": "/api/admin/records", "dest": "/api/admin.py" },
    { "src": "/api/admin", "dest": "/api/admin.py" },
    { "src": "/(.*)", "dest": "/frontend/$1" }
  ]
}
```

Most specific to least specific.

### ✅ 3. Use Catch-All Handlers

```python
@app.api_route('/{path_name:path}', methods=['GET', 'POST', 'PUT', 'DELETE'])
async def handler(request: Request, path_name: str):
    # Route based on path and method
    if request.method == 'POST' and path_name == 'api/admin':
        return await login(request)
    # ... more routing
```

Handles all HTTP methods and paths in one function.

### ✅ 4. Add Health Checks

```python
@app.get('/')
async def health():
    return JSONResponse({'status': 'ok'})
```

Vercel can check if your function is healthy.

## Complete Example

Here's a complete working example for a FastAPI admin API:

**vercel.json**:
```json
{
  "version": 2,
  "builds": [
    { "src": "api/admin.py", "use": "@vercel/python" },
    { "src": "frontend/**", "use": "@vercel/static" }
  ],
  "routes": [
    { "src": "/api/admin/(.*)", "dest": "/api/admin.py" },
    { "src": "/api/admin", "dest": "/api/admin.py" },
    { "src": "/", "dest": "/frontend/index.html" },
    { "src": "/(.*)", "dest": "/frontend/$1" }
  ]
}
```

**api/admin.py**:
```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

@app.post('/{path_name:path}')
async def post_handler(request: Request, path_name: str):
    print(f"[admin] POST: {path_name}")
    
    if path_name == 'api/admin':
        # Handle authentication
        body = await request.json()
        password = body.get('password')
        # ... verify password
        return JSONResponse({'authenticated': True})
    
    elif path_name == 'api/admin/records':
        # Handle records CRUD
        body = await request.json()
        # ... handle record operations
        return JSONResponse({'status': 'ok'})
    
    return JSONResponse({'error': 'Not found'}, status_code=404)

@app.get('/')
async def health():
    return JSONResponse({'status': 'ok', 'service': 'admin'})
```

## Testing

### Local Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Run FastAPI app
uvicorn api.admin:app --reload --port 8000

# Test endpoint
curl -X POST http://localhost:8000/api/admin \
  -H "Content-Type: application/json" \
  -d '{"password":"test"}'
```

### Vercel Testing

```bash
# Install Vercel CLI
npm i -g vercel

# Run locally with Vercel dev server
vercel dev

# Test endpoint
curl -X POST http://localhost:3000/api/admin \
  -H "Content-Type: application/json" \
  -d '{"password":"test"}'
```

## Summary

1. **Vercel passes full paths** to your app (e.g., `api/admin`, not `/`)
2. **Use catch-all routes** (`/{path_name:path}`) to handle all requests
3. **No adapter needed** - FastAPI/Flask work natively with `@vercel/python`
4. **Route order matters** - specific routes before catch-all routes
5. **Add logging** to debug what paths your app receives
6. **Test with `vercel dev`** to simulate production routing locally

## Resources

- [Vercel Python Runtime](https://vercel.com/docs/functions/runtimes/python)
- [Vercel Routing Configuration](https://vercel.com/docs/projects/project-configuration#routes)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Flask Documentation](https://flask.palletsprojects.com/)
