from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, JSON, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

try:
    from ..database.session import Base
except ImportError:  # pragma: no cover - supports running from backend/ as main:app
    from database.session import Base

JsonDocument = JSON().with_variant(JSONB, "postgresql")


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    url: Mapped[str] = mapped_column(String(2048), unique=True, nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(String(600), nullable=True)
    cuisine: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prep_time: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cook_time: Mapped[str | None] = mapped_column(String(50), nullable=True)
    total_time: Mapped[str | None] = mapped_column(String(50), nullable=True)
    servings: Mapped[str | None] = mapped_column(String(50), nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(50), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    source_domain: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    ingredients: Mapped[list[dict[str, Any]]] = mapped_column(JsonDocument, default=list)
    instructions: Mapped[list[str]] = mapped_column(JsonDocument, default=list)
    nutrition: Mapped[dict[str, Any] | None] = mapped_column(JsonDocument, nullable=True)
    substitutions: Mapped[list[dict[str, Any]]] = mapped_column(JsonDocument, default=list)
    shopping_list: Mapped[list[dict[str, Any]]] = mapped_column(JsonDocument, default=list)
    related_recipes: Mapped[list[str]] = mapped_column(JsonDocument, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
