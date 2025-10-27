# Running the Application

This project now uses a **unified FastAPI application** that works for both local development and Vercel deployment.

## Local Development

Run the FastAPI app with Uvicorn:

```bash
python main.py
```

Or use Uvicorn directly:

```bash
uvicorn main:app --reload --port 7860
```

The application will be available at `http://localhost:7860`

## Vercel Deployment

The same FastAPI app is used on Vercel. The `api/admin.py` file simply imports the app from `main.py`.

Deploy with:

```bash
vercel --prod
```

## Benefits of Unified App

- **Single Source of Truth**: All API logic is in `main.py`
- **No Duplication**: Changes only need to be made once
- **Consistent Behavior**: Local and production environments use the same code
- **Easier Maintenance**: Only one file to update for API changes

## Old Files

- `app.py` (Flask) - No longer used, can be deleted
- Previous `api/admin.py` had duplicated logic - now just imports from `main.py`
