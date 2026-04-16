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


class LLMTemporaryServiceError(LLMServiceError):
    pass


def load_prompt(name: str) -> str:
    prompt_path = PROMPT_DIR / name
    if not prompt_path.exists():
        raise LLMServiceError(f"Prompt file not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")


def build_model(model_name: str | None = None) -> ChatGoogleGenerativeAI:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise LLMServiceError("GEMINI_API_KEY is not configured.")

    return ChatGoogleGenerativeAI(
        model=model_name or settings.gemini_model,
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


def is_model_temporarily_unavailable(error: Exception) -> bool:
    message = str(error).lower()
    return (
        "503" in message
        or "unavailable" in message
        or "high demand" in message
        or "overloaded" in message
    )


def is_model_permission_error(error: Exception) -> bool:
    message = str(error).lower()
    return "permission_denied" in message or "api key was reported as leaked" in message


def retry_limit_for_error(error: Exception, settings) -> int:
    if is_model_temporarily_unavailable(error):
        return max(settings.llm_max_retries, settings.llm_unavailable_retries)
    return settings.llm_max_retries


def sleep_for_retry(attempt: int, base_backoff_seconds: float) -> None:
    time.sleep(base_backoff_seconds * (2 ** (attempt - 1)))


def invoke_with_model(prompt: str, model_name: str) -> dict[str, Any]:
    settings = get_settings()
    model = build_model(model_name)
    last_error: Exception | None = None
    max_attempts = settings.llm_max_retries
    attempt = 0

    while attempt < max_attempts:
        attempt += 1
        try:
            response = model.invoke(prompt)
            parsed = parse_json_response(stringify_content(response.content))
            if not isinstance(parsed, dict):
                raise LLMParsingError("Model response JSON must be an object.")
            return parsed
        except Exception as exc:  # pragma: no branch
            last_error = exc
            max_attempts = retry_limit_for_error(exc, settings)
            if is_model_permission_error(exc):
                break
            if attempt >= max_attempts:
                break
            sleep_for_retry(attempt, settings.llm_retry_backoff_seconds)

    if isinstance(last_error, LLMParsingError):
        raise LLMServiceError(str(last_error)) from last_error
    if last_error and is_model_temporarily_unavailable(last_error):
        raise LLMTemporaryServiceError(
            f"Gemini is temporarily unavailable for model '{model_name}'. Please retry shortly."
        ) from last_error
    raise LLMServiceError(f"Gemini request failed: {last_error}") from last_error


def invoke_json_prompt(prompt_name: str, **variables: str) -> dict[str, Any]:
    settings = get_settings()
    template = load_prompt(prompt_name)
    prompt = template
    for key, value in variables.items():
        prompt = prompt.replace(f"{{{key}}}", value)

    model_names = [settings.gemini_model]
    if settings.gemini_fallback_model and settings.gemini_fallback_model != settings.gemini_model:
        model_names.append(settings.gemini_fallback_model)

    last_error: Exception | None = None
    for model_name in model_names:
        try:
            return invoke_with_model(prompt, model_name)
        except LLMTemporaryServiceError as exc:
            last_error = exc
            if model_name == model_names[-1]:
                break
        except LLMServiceError as exc:
            raise exc from exc

    raise LLMTemporaryServiceError(str(last_error)) from last_error


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
