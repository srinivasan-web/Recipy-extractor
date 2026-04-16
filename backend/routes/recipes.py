from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from pydantic import ValidationError

try:
    from ..database.session import get_database_status, get_db
    from ..models.recipe import Recipe
    from ..schemas.recipe import (
        CuisineBreakdown,
        DashboardOverview,
        ExtractRequest,
        RecipeCreate,
        RecipeListItem,
        RecipeRead,
        build_manual_source_url,
    )
    from ..services.llm import LLMServiceError, extract_recipe_bundle
    from ..services.llm import LLMTemporaryServiceError
    from ..services.parser import normalize_recipe_payload
    from ..services.scraper import ScrapedPage, ScraperError, scrape_recipe_page
except ImportError:  # pragma: no cover - supports running from backend/ as main:app
    from database.session import get_database_status, get_db
    from models.recipe import Recipe
    from schemas.recipe import (
        CuisineBreakdown,
        DashboardOverview,
        ExtractRequest,
        RecipeCreate,
        RecipeListItem,
        RecipeRead,
        build_manual_source_url,
    )
    from services.llm import LLMServiceError, extract_recipe_bundle
    from services.llm import LLMTemporaryServiceError
    from services.parser import normalize_recipe_payload
    from services.scraper import ScrapedPage, ScraperError, scrape_recipe_page

router = APIRouter(tags=["recipes"])


def serialize_recipe(recipe: Recipe, *, cached: bool = False) -> RecipeRead:
    payload = RecipeRead.model_validate(recipe)
    return payload.model_copy(update={"cached": cached})


def build_recipe_summary(payload: dict, scraped_page: ScrapedPage | None) -> str | None:
    if payload.get("summary"):
        return str(payload["summary"]).strip()[:280] or None
    if scraped_page and scraped_page.description:
        return scraped_page.description.strip()[:280] or None

    ingredients = payload.get("ingredients") or []
    ingredient_names = [item.get("item") for item in ingredients if isinstance(item, dict) and item.get("item")]
    preview = ", ".join(ingredient_names[:3])

    title = payload.get("title") or "This recipe"
    cuisine = payload.get("cuisine")
    servings = payload.get("servings")
    parts = [f"{title} is a {cuisine.lower()} recipe" if cuisine else f"{title} is a recipe"]
    if preview:
        parts.append(f"featuring {preview}")
    if servings:
        parts.append(f"that serves {servings}")
    summary = ", ".join(parts).replace("recipe, that", "recipe that")
    return summary[:280]


def enrich_recipe_payload(source_url: str, payload: dict, scraped_page: ScrapedPage | None) -> dict:
    normalized = normalize_recipe_payload(payload)
    normalized["source_domain"] = (
        normalized.get("source_domain")
        or (scraped_page.domain if scraped_page else None)
        or urlparse(source_url).netloc
        or None
    )
    normalized["image_url"] = (scraped_page.image_url if scraped_page else None) or normalized.get("image_url")
    normalized["summary"] = build_recipe_summary(normalized, scraped_page)

    if scraped_page and scraped_page.title and not normalized.get("title"):
        normalized["title"] = scraped_page.title

    return normalized


@router.get("/health", tags=["meta"])
def health_check(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database health check failed: {exc}",
        ) from exc
    database_status = get_database_status()
    return {
        "status": "ok",
        "database": "connected",
        "database_mode": "fallback-sqlite" if database_status["fallback_active"] else "primary",
    }


@router.get("/dashboard", response_model=DashboardOverview)
def dashboard_overview(db: Session = Depends(get_db)) -> DashboardOverview:
    total_recipes = db.scalar(select(func.count(Recipe.id))) or 0
    cuisines_tracked = db.scalar(select(func.count(func.distinct(Recipe.cuisine))).where(Recipe.cuisine.is_not(None))) or 0
    recipes_with_images = db.scalar(select(func.count(Recipe.id)).where(Recipe.image_url.is_not(None))) or 0

    ingredient_counts = db.scalars(select(Recipe.ingredients)).all()
    average_ingredients = 0.0
    if ingredient_counts:
        average_ingredients = round(
            sum(len(ingredients or []) for ingredients in ingredient_counts) / len(ingredient_counts),
            1,
        )

    top_cuisines_rows = db.execute(
        select(Recipe.cuisine, func.count(Recipe.id))
        .where(Recipe.cuisine.is_not(None))
        .group_by(Recipe.cuisine)
        .order_by(func.count(Recipe.id).desc(), Recipe.cuisine.asc())
        .limit(4)
    ).all()
    top_cuisines = [
        CuisineBreakdown(cuisine=row[0], count=row[1])
        for row in top_cuisines_rows
        if row[0]
    ]

    latest_recipe = db.scalar(select(Recipe).order_by(Recipe.created_at.desc(), Recipe.id.desc()).limit(1))

    return DashboardOverview(
        total_recipes=total_recipes,
        cuisines_tracked=cuisines_tracked,
        recipes_with_images=recipes_with_images,
        average_ingredients=average_ingredients,
        latest_recipe=RecipeListItem.model_validate(latest_recipe) if latest_recipe else None,
        top_cuisines=top_cuisines,
    )


@router.post("/extract", response_model=RecipeRead, status_code=status.HTTP_201_CREATED)
def extract_recipe(request: ExtractRequest, db: Session = Depends(get_db)) -> RecipeRead:
    source_url = str(request.url) if request.url else build_manual_source_url(request.raw_text or "")

    existing_recipe = db.scalar(select(Recipe).where(Recipe.url == source_url))
    if existing_recipe:
        return serialize_recipe(existing_recipe, cached=True)

    source_text: str
    scraped_page: ScrapedPage | None = None
    if request.raw_text and request.raw_text.strip():
        source_text = request.raw_text.strip()
    elif request.url:
        try:
            scraped_page = scrape_recipe_page(str(request.url))
        except ScraperError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"{exc} "
                    "You can also retry by sending `raw_text` directly to `/api/extract` if the site blocks scraping."
                ),
            ) from exc
        source_text = scraped_page.text
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either a recipe URL or raw_text.",
        )

    try:
        llm_payload = extract_recipe_bundle(source_text)
    except LLMTemporaryServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except LLMServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    try:
        recipe_in = RecipeCreate(url=source_url, **enrich_recipe_payload(source_url, llm_payload, scraped_page))
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM returned an invalid recipe schema: {exc}",
        ) from exc

    recipe = Recipe(**recipe_in.model_dump(mode="json"))
    try:
        db.add(recipe)
        db.commit()
        db.refresh(recipe)
    except IntegrityError:
        db.rollback()
        existing_recipe = db.scalar(select(Recipe).where(Recipe.url == source_url))
        if existing_recipe:
            return serialize_recipe(existing_recipe, cached=True)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A recipe with this URL already exists.",
        ) from None
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while saving recipe: {exc}",
        ) from exc

    return serialize_recipe(recipe)


@router.get("/recipes", response_model=list[RecipeListItem])
def list_recipes(
    search: str | None = Query(default=None, max_length=120),
    cuisine: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=24, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[RecipeListItem]:
    query = select(Recipe)

    if search:
        search_term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Recipe.title.ilike(search_term),
                Recipe.cuisine.ilike(search_term),
                Recipe.url.ilike(search_term),
                Recipe.source_domain.ilike(search_term),
            )
        )

    if cuisine and cuisine != "All":
        query = query.where(Recipe.cuisine == cuisine)

    recipes = db.scalars(query.order_by(Recipe.created_at.desc(), Recipe.id.desc()).limit(limit)).all()
    return [RecipeListItem.model_validate(recipe) for recipe in recipes]


@router.get("/recipes/{recipe_id}", response_model=RecipeRead)
def get_recipe(recipe_id: int, db: Session = Depends(get_db)) -> RecipeRead:
    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found.")
    return serialize_recipe(recipe)
