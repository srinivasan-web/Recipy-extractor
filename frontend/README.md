# Frontend

This is a lightweight React + Vite client for the recipe extraction workflow.

Run:

```bash
npm install
npm run dev
```

The app expects the FastAPI backend at `http://localhost:8000/api` unless `VITE_API_BASE` is set.

Copy `.env.example` to `.env` when you want to point the UI at a deployed API.
