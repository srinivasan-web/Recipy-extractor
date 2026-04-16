from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Any

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator


class IngredientItem(BaseModel):
    quantity: str | None = None
    unit: str | None = None
    item: str | None = None


class SubstitutionItem(BaseModel):
    ingredient: str | None = None
    alternatives: list[str] = Field(default_factory=list)
    notes: str | None = None


class ShoppingListItem(BaseModel):
    item: str | None = None
    quantity: str | None = None
    category: str | None = None


class RecipePayload(BaseModel):
    title: str | None = None
    summary: str | None = None
    cuisine: str | None = None
    prep_time: str | None = None
    cook_time: str | None = None
    total_time: str | None = None
    servings: str | None = None
    difficulty: str | None = None
    image_url: str | None = None
    source_domain: str | None = None
    ingredients: list[IngredientItem] = Field(default_factory=list)
    instructions: list[str] = Field(default_factory=list)
    nutrition: dict[str, Any] | None = None
    substitutions: list[SubstitutionItem] = Field(default_factory=list)
    shopping_list: list[ShoppingListItem] = Field(default_factory=list)
    related_recipes: list[str] = Field(default_factory=list)


class RecipeCreate(RecipePayload):
    url: str


class RecipeRead(RecipeCreate):
    id: int
    created_at: datetime
    cached: bool = False

    model_config = ConfigDict(from_attributes=True)


class RecipeListItem(BaseModel):
    id: int
    url: str
    title: str | None = None
    summary: str | None = None
    cuisine: str | None = None
    total_time: str | None = None
    servings: str | None = None
    image_url: str | None = None
    source_domain: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CuisineBreakdown(BaseModel):
    cuisine: str
    count: int


class DashboardOverview(BaseModel):
    total_recipes: int
    cuisines_tracked: int
    recipes_with_images: int
    average_ingredients: float
    latest_recipe: RecipeListItem | None = None
    top_cuisines: list[CuisineBreakdown] = Field(default_factory=list)


class ExtractRequest(BaseModel):
    url: AnyHttpUrl | None = None
    raw_text: str | None = None

    @model_validator(mode="after")
    def validate_source(self) -> "ExtractRequest":
        if self.url is None and not (self.raw_text and self.raw_text.strip()):
            raise ValueError("Provide either a recipe URL or raw_text.")
        return self


def build_manual_source_url(raw_text: str) -> str:
    digest = sha256(raw_text.encode("utf-8")).hexdigest()[:16]
    return f"manual://recipe/{digest}"
