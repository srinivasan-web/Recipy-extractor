from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    from .database.config import get_settings
    from .database.session import init_db
    from .routes.recipes import router as recipe_router
except ImportError:  # pragma: no cover - supports running from backend/ as main:app
    from database.config import get_settings
    from database.session import init_db
    from routes.recipes import router as recipe_router

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Recipe extraction pipeline powered by FastAPI, scraping, and Gemini.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list(),
    allow_origin_regex=settings.cors_allowed_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recipe_router, prefix=settings.api_prefix)


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {"message": "Recipe Extractor API is running."}
