# Recipe Extractor & Meal Planner

A full-stack app that turns recipe URLs into structured data you can search, review, and reuse.

Stack:

`React + Vite -> FastAPI -> scraper/parser services -> Gemini -> SQLAlchemy`

## What it does

1. Accepts a recipe URL from the frontend.
2. Scrapes the page and extracts readable content.
3. Sends the cleaned content to Gemini for structured recipe output.
4. Stores the result for later reuse.
5. Shows history, dashboard stats, and recipe details in the UI.

## Project structure

```text
backend/       FastAPI app, scraping, parsing, persistence
frontend/      React + Vite client
prompts/       Prompt templates used by the LLM flow
sample_data/   Example URLs and sample response data
tests/         Backend end-to-end tests
render.yaml    Backend deployment config
```

## Local setup

### 1. Create a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### 2. Install backend dependencies

```powershell
pip install -r requirements.txt
```

The root `requirements.txt` points to [backend/requirements.txt](backend/requirements.txt), so one install command is enough.

### 3. Add backend environment values

```powershell
copy backend\.env.example backend\.env
```

Important variables:

- `GEMINI_API_KEY`
- `GEMINI_MODEL=gemini-2.5-flash`
- `DATABASE_URL`
- `LLM_MAX_RETRIES`
- `LLM_RETRY_BACKOFF_SECONDS`

Notes:

- The backend can read env values from either `.env` in the project root or `backend/.env`.
- PostgreSQL URLs are normalized automatically for SQLAlchemy.
- If `DATABASE_URL` is not set, the app can still boot locally with SQLite-based development defaults.

### 4. Start the backend

From the project root:

```powershell
python -m uvicorn backend.main:app --reload
```

If you are already inside `backend/`, use:

```powershell
python -m uvicorn main:app --reload
```

### 5. Start the frontend

```powershell
cd frontend
npm install
npm run dev
```

Optional frontend env:

```text
VITE_API_BASE=http://localhost:8000/api
```

The example file is [frontend/.env.example](frontend/.env.example).

## API routes

- `POST /api/extract`
- `GET /api/recipes`
- `GET /api/recipes/{id}`
- `GET /api/dashboard`
- `GET /api/health`

`GET /api/health` also checks database connectivity.

## Prompt files

Prompt templates live in [prompts](prompts):

- `recipe_extraction.txt`
- `nutrition.txt`
- `substitutions.txt`
- `shopping_list.txt`

This keeps extraction behavior easy to update without mixing prompt text into application code.

## Deployment

### Backend

- Use [render.yaml](render.yaml) as the starter config.
- Set `DATABASE_URL`, `GEMINI_API_KEY`, and `GEMINI_MODEL` in your hosting environment.
- Start command:

```text
uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

### Frontend

- Deploy the `frontend/` folder.
- Set `VITE_API_BASE` to your backend URL plus `/api`.
- Build with `npm run build`.

## Sample data

Example URLs and a sample response are in [sample_data](sample_data).
