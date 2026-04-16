# Recipe Extractor & Meal Planner

A production-leaning starter for the assignment workflow:

`React -> FastAPI -> Scraper -> Gemini via LangChain -> SQLAlchemy/PostgreSQL`

The repo is scaffolded to handle the full pipeline:

1. Accept a recipe URL from the frontend
2. Scrape the page and normalize readable text
3. Ask Gemini for structured JSON with strict prompts
4. Cache repeated URLs in the database
5. Return the structured recipe and render it in the UI
6. Store image-rich metadata, summaries, and source domains for a more browsable recipe library

## Repo layout

```text
backend/
frontend/
prompts/
sample_data/
render.yaml
README.md
```

## Backend setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy backend\.env.example backend\.env
uvicorn backend.main:app --reload
```

Important environment variables:

- `DATABASE_URL=postgresql://recipe_user:recipe_pass@localhost:5432/recipe_planner`
- `GEMINI_API_KEY=your_google_ai_api_key`
- `GEMINI_MODEL=gemini-2.5-flash`
- `LLM_MAX_RETRIES=3`
- `LLM_RETRY_BACKOFF_SECONDS=1`

Notes:

- The backend loads environment variables from either the repo root `.env` or `backend/.env`.
- `postgres://...` and `postgresql://...` URLs are normalized automatically to SQLAlchemy's `postgresql+psycopg://...` format.
- The backend defaults to a shared in-memory SQLite database so the scaffold can boot locally without PostgreSQL.
- Local extraction history persists for the lifetime of the running backend process; set `DATABASE_URL` to PostgreSQL for durable storage.
- For the real assignment submission, switch `DATABASE_URL` to PostgreSQL.

## PostgreSQL setup

Use Supabase or Railway for the real submission.

1. Create a hosted PostgreSQL database.
2. Copy the connection string into `DATABASE_URL`.
3. Run the SQL in [backend/database/schema.sql](backend/database/schema.sql) if you want to provision the table manually.

The app can also create the table automatically on startup through SQLAlchemy.

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Optional frontend env:

```bash
VITE_API_BASE=http://localhost:8000/api
```

The matching example file is [frontend/.env.example](frontend/.env.example).

## API endpoints

- `POST /api/extract`
- `GET /api/recipes`
- `GET /api/recipes/{id}`
- `GET /api/dashboard`
- `GET /api/health`

`GET /api/health` also verifies database connectivity, which is useful during deployment checks.

## LLM strategy

Prompts are split into dedicated files in [`prompts/`](prompts):

- `recipe_extraction.txt`
- `nutrition.txt`
- `substitutions.txt`
- `shopping_list.txt`

This keeps the core extraction focused while allowing targeted enrichment passes and easier prompt iteration during interviews.

Gemini calls use retry/backoff and JSON parsing safeguards so transient provider failures or malformed responses do not immediately crash the request flow.

## Advanced features included

Repeated URLs are cached. If a recipe URL already exists in the database, the backend returns the stored record instead of scraping and invoking Gemini again.

The app now also stores image URLs, source domains, and generated summaries so the frontend can provide a faster, more visual dashboard experience with searchable history cards and overview metrics.

## Deployment

### Backend on Render

- A starter Render config is included in [render.yaml](render.yaml).
- Set `DATABASE_URL`, `GEMINI_API_KEY`, and `GEMINI_MODEL` in Render.
- The service starts with `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`.

### Frontend on Vercel

- Import the `frontend/` directory as the Vercel project root.
- Set `VITE_API_BASE` to your deployed backend URL plus `/api`.
- Run the frontend build with `npm run build`.

## Sample data

Sample URLs and a mock response shape live in [`sample_data/`](sample_data).

# Recipy-extractor
