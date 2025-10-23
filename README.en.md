# 🧾 Resume Agent — Quick Guide

**Languages:** [English](README.md) | [简体中文](README.zh.md)

This is a small RAG (Retrieval-Augmented Generation) / resume assistant project (Resume Agent).
Core concept: Convert structured project or resume information (stored in Neon/Postgres `projects` table) into vectors and save them in Upstash Vector. The frontend/Serverless retrieves relevant content during queries and uses LLM to generate data-based responses.

This repository contains:
- Data reading and migration tools: `migrate_utils.py` (can be called by CLI, CI, serverless)
- Local upsert script: `upsert_projects_to_vector.py` (can be run manually locally or in CI)
- Local development frontend/service: `app.py` and `frontend/` (simple chat UI for local development)
- Serverless endpoint (deployable to Vercel): `api/upsert-projects.py` (for triggering one-time upsert)

## Main Features

- Read project/resume information from `projects` table and build text and metadata for vectorization
- Upload (upsert) built documents to Upstash Vector
- Provide local demo frontend (chat UI) for connecting to deployed vector retrieval + LLM

---

## Quick Start (Local Development)

1. Clone the repository and enter the directory:

```powershell
git clone <your-repo-url>
cd resume_agent
```

2. Install dependencies (recommend using venv):

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

3. Prepare environment variables (example `.env` or PowerShell):

Required environment variables:

- `DATABASE_URL` — Neon/Postgres connection string (e.g., postgresql://...)
- `UPSTASH_VECTOR_REST_URL` — Upstash Vector REST API URL
- `UPSTASH_VECTOR_REST_TOKEN` — Upstash Vector REST token
- `VECTOR_DB_TYPE` — defaults to `upstash`

Optional (depending on your LLM usage):

- `GROQ_API_KEY` (if using Groq)
- `MIGRATION_KEY` (if you want to use key protection in serverless endpoint)

PowerShell temporary example:

```powershell
$env:DATABASE_URL = "postgresql://user:pw@host:port/dbname"
$env:UPSTASH_VECTOR_REST_URL = "https://..."
$env:UPSTASH_VECTOR_REST_TOKEN = "xxxx"
```

4. (Optional) Initialize/populate sample data to `projects` table:

If you need to quickly populate sample projects, run `db_seed_projects.py` in the repository (ensure `DATABASE_URL` is set):

```powershell
python db_seed_projects.py
```

5. Run local upsert (upload `projects` table to Upstash Vector):

```powershell
python upsert_projects_to_vector.py
```

The script will read the database and call the logic in `migrate_utils`, upload documents to Upstash, and print statistics in the console (total entries, upserted, errors).

6. Start local frontend (for development)

```powershell
python app.py
# Then open http://127.0.0.1:5000 in your browser
```

---

## Manual Trigger Upsert on GitHub Actions

The repository includes a manually triggered workflow: `.github/workflows/upsert.yml`, for executing `upsert_projects_to_vector.py` in CI.

Usage steps:

1. Add to repository Settings → Secrets:
   - `DATABASE_URL`
   - `UPSTASH_VECTOR_REST_URL`
   - `UPSTASH_VECTOR_REST_TOKEN`
   - Optional: `GROQ_API_KEY`, `MIGRATION_KEY`

2. On the GitHub repository page, open Actions → select "Upsert Projects to Vector" → click `Run workflow`.

This workflow will checkout, install dependencies and run `python upsert_projects_to_vector.py` (you can later modify the workflow to accept parameters like `--dry-run` or `project_id`).

---

## Serverless / Deployment Notes

- `api/upsert-projects.py` is a FastAPI serverless endpoint (suitable for Vercel) for manually triggering one upsert. Serverless typically isn't suitable for long-running batch tasks (timeout limitations), so it's recommended to run large-scale or regular upserts in CI / Agent.
- If you deploy the frontend to Vercel (static + serverless read API), ensure Upstash and Postgres are accessible (Vercel should configure corresponding Secrets), and upload operations are performed by CI or regular agents.

---

## Debugging and Extension Suggestions

- dry-run: I can add a `--dry-run` flag to `upsert_projects_to_vector.py` to print the enriched_text and metadata to be uploaded without writing. This is very useful for content review.
- Batching and retry: If there are many projects, batch processing and retry strategies should be adopted in migration logic (extension points are reserved in `migrate_utils.py`).
- id namespace: Migration uses namespaced ids (e.g., `project:<id>`) to avoid conflicts with other datasets.

---

## Developer Tips

- Code entry points: `migrate_utils.py` (migration logic), `upsert_projects_to_vector.py` (CLI), `api/upsert-projects.py` (serverless endpoint), `app.py` (local frontend).
- If you need me to implement `--dry-run`, upsert by project id, or parameterized Actions input functionality to the workflow, tell me the parameters and default behavior you want, and I'll continue implementing and verifying.

---

If you need me to now:

1) Add `--dry-run` to `upsert_projects_to_vector.py`;
2) Make workflow support `project_id` or `dry-run` parameters;
3) Change local frontend to call serverless read API (instead of local rag queries),

Tell me the number, and I'll continue implementing and do a local verification (syntax check / quick run).