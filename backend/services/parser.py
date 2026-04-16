from __future__ import annotations

import json
import re
from typing import Any


class LLMParsingError(ValueError):
    pass


NUTRITION_KEYS = (
    "calories",
    "protein",
    "carbohydrates",
    "fat",
    "fiber",
    "sugar",
    "sodium",
)


def parse_json_response(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.DOTALL)

    candidates = [text]
    json_match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if json_match:
        candidates.insert(0, json_match.group(0))

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    raise LLMParsingError("Model response did not contain valid JSON.")


def normalize_recipe_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = payload.copy()
    normalized.setdefault("summary", None)
    normalized.setdefault("image_url", None)
    normalized.setdefault("source_domain", None)
    normalized.setdefault("ingredients", [])
    normalized.setdefault("instructions", [])
    normalized.setdefault("substitutions", [])
    normalized.setdefault("shopping_list", [])
    normalized.setdefault("related_recipes", [])
    normalized.setdefault("nutrition", None)

    normalized["summary"] = normalize_summary(
        normalized.get("summary")
        or normalized.get("description")
        or normalized.get("excerpt")
        or normalized.get("meta_description")
    )
    normalized["image_url"] = normalize_image_value(
        normalized.get("image_url")
        or normalized.get("imageUrl")
        or normalized.get("image")
        or normalized.get("thumbnail_url")
        or normalized.get("thumbnailUrl")
        or normalized.get("thumbnail")
    )
    normalized["source_domain"] = stringify_optional(
        normalized.get("source_domain")
        or normalized.get("sourceDomain")
        or normalized.get("domain")
    )

    ingredients = normalized.get("ingredients")
    if isinstance(ingredients, list):
        normalized["ingredients"] = [normalize_ingredient(item) for item in ingredients]

    shopping_list = normalized.get("shopping_list")
    if isinstance(shopping_list, list):
        normalized["shopping_list"] = [normalize_shopping_item(item) for item in shopping_list]

    instructions = normalized.get("instructions")
    if isinstance(instructions, list):
        normalized["instructions"] = [stringify_scalar(item) for item in instructions if item is not None]

    related_recipes = normalized.get("related_recipes")
    if isinstance(related_recipes, list):
        normalized["related_recipes"] = [stringify_scalar(item) for item in related_recipes if item is not None]

    substitutions = normalized.get("substitutions")
    if isinstance(substitutions, list):
        normalized["substitutions"] = [normalize_substitution(item) for item in substitutions]

    normalized["nutrition"] = normalize_nutrition(normalized.get("nutrition"))

    return normalized


def stringify_scalar(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def stringify_optional(value: Any) -> str | None:
    if value is None:
        return None
    text = stringify_scalar(value)
    return text or None


def normalize_ingredient(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"quantity": None, "unit": None, "item": stringify_optional(item)}
    return {
        "quantity": stringify_optional(item.get("quantity")),
        "unit": stringify_optional(item.get("unit")),
        "item": stringify_optional(item.get("item")),
    }


def normalize_substitution(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {
            "ingredient": stringify_optional(item),
            "alternatives": [],
            "notes": None,
        }

    alternatives = item.get("alternatives", [])
    if isinstance(alternatives, list):
        normalized_alternatives = [stringify_scalar(value) for value in alternatives if value is not None]
    elif alternatives is None:
        normalized_alternatives = []
    else:
        normalized_alternatives = [stringify_scalar(alternatives)]

    return {
        "ingredient": stringify_optional(item.get("ingredient")),
        "alternatives": normalized_alternatives,
        "notes": stringify_optional(item.get("notes")),
    }


def normalize_shopping_item(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {
            "item": stringify_optional(item),
            "quantity": None,
            "category": None,
        }
    return {
        "item": stringify_optional(item.get("item")),
        "quantity": stringify_optional(item.get("quantity")),
        "category": stringify_optional(item.get("category")),
    }


def normalize_nutrition(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None

    if isinstance(value, dict):
        return {stringify_scalar(key): stringify_optional(item) for key, item in value.items()}

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        return {key: extract_nutrition_value(text, key) for key in NUTRITION_KEYS}

    return {"summary": stringify_scalar(value)}


def normalize_summary(value: Any) -> str | None:
    text = stringify_optional(value)
    if not text:
        return None
    return text[:280]


def normalize_image_value(value: Any) -> str | None:
    if value is None:
        return None

    if isinstance(value, str):
        text = value.strip()
        return text or None

    if isinstance(value, list):
        for item in value:
            candidate = normalize_image_value(item)
            if candidate:
                return candidate
        return None

    if isinstance(value, dict):
        for key in ("url", "src", "@id"):
            candidate = normalize_image_value(value.get(key))
            if candidate:
                return candidate
        return None

    return stringify_optional(value)


def extract_nutrition_value(text: str, key: str) -> str | None:
    patterns = {
        "calories": r"(\d+(?:\.\d+)?)\s*calories?\b",
        "protein": r"(\d+(?:\.\d+)?)\s*(?:grams?|g)\s+protein\b",
        "carbohydrates": r"(\d+(?:\.\d+)?)\s*(?:grams?|g)\s+carbohydrates?\b",
        "fat": r"(\d+(?:\.\d+)?)\s*(?:grams?|g)\s+fat\b",
        "fiber": r"(\d+(?:\.\d+)?)\s*(?:grams?|g)\s+fiber\b",
        "sugar": r"(\d+(?:\.\d+)?)\s*(?:grams?|g)\s+sugar\b",
        "sodium": r"(\d+(?:\.\d+)?)\s*(?:milligrams?|mg)\s+of\s+sodium\b",
    }
    match = re.search(patterns[key], text, flags=re.IGNORECASE)
    if not match:
        return None

    unit = {
        "calories": "calories",
        "protein": "g",
        "carbohydrates": "g",
        "fat": "g",
        "fiber": "g",
        "sugar": "g",
        "sodium": "mg",
    }[key]
    return f"{match.group(1)} {unit}"
