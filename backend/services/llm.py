from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import ValidationError

try:
    from ..database.config import get_settings
    from ..schemas.recipe import RecipePayload
    from .parser import LLMParsingError, normalize_recipe_payload, parse_json_response
except ImportError:  # pragma: no cover - supports running from backend/ as main:app
    from database.config import get_settings
    from schemas.recipe import RecipePayload
    from services.parser import LLMParsingError, normalize_recipe_payload, parse_json_response

PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"
MAX_SOURCE_CHARS = 20000


class LLMServiceError(RuntimeError):
    pass


def load_prompt(name: str) -> str:
    prompt_path = PROMPT_DIR / name
    if not prompt_path.exists():
        raise LLMServiceError(f"Prompt file not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")


def build_model() -> ChatGoogleGenerativeAI:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise LLMServiceError("GEMINI_API_KEY is not configured.")

    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=0,
    )


def stringify_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and "text" in part:
                parts.append(str(part["text"]))
            else:
                parts.append(str(part))
        return "\n".join(parts)
    return str(content)


def invoke_json_prompt(prompt_name: str, **variables: str) -> dict[str, Any]:
    settings = get_settings()
    model = build_model()
    template = load_prompt(prompt_name)
    prompt = template
    for key, value in variables.items():
        prompt = prompt.replace(f"{{{key}}}", value)

    last_error: Exception | None = None
    for attempt in range(1, settings.llm_max_retries + 1):
        try:
            response = model.invoke(prompt)
            parsed = parse_json_response(stringify_content(response.content))
            if not isinstance(parsed, dict):
                raise LLMParsingError("Model response JSON must be an object.")
            return parsed
        except Exception as exc:  # pragma: no branch
            last_error = exc
            if attempt == settings.llm_max_retries:
                break
            time.sleep(settings.llm_retry_backoff_seconds * attempt)

    if isinstance(last_error, LLMParsingError):
        raise LLMServiceError(str(last_error)) from last_error
    raise LLMServiceError(f"Gemini request failed: {last_error}") from last_error


def validate_recipe_bundle(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        validated = RecipePayload.model_validate(payload)
    except ValidationError as exc:
        raise LLMServiceError(f"LLM returned an invalid recipe payload: {exc}") from exc
    return validated.model_dump(mode="json")


def extract_recipe_bundle(recipe_text: str) -> dict[str, Any]:
    truncated_text = recipe_text[:MAX_SOURCE_CHARS]

    recipe_payload = invoke_json_prompt(
        "recipe_extraction.txt",
        recipe_text=truncated_text,
    )
    normalized_recipe = validate_recipe_bundle(normalize_recipe_payload(recipe_payload))
    recipe_json = json.dumps(normalized_recipe, ensure_ascii=False, indent=2)

    nutrition_payload = invoke_json_prompt("nutrition.txt", recipe_json=recipe_json)
    substitutions_payload = invoke_json_prompt("substitutions.txt", recipe_json=recipe_json)
    shopping_payload = invoke_json_prompt("shopping_list.txt", recipe_json=recipe_json)

    normalized_recipe["nutrition"] = nutrition_payload.get("nutrition")
    normalized_recipe["substitutions"] = substitutions_payload.get("substitutions", [])
    normalized_recipe["shopping_list"] = shopping_payload.get("shopping_list", [])

    return validate_recipe_bundle(normalized_recipe)
