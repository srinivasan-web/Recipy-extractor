from __future__ import annotations

import importlib
import os
import sys
import unittest
from dataclasses import dataclass
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError


def clear_backend_modules() -> None:
    for module_name in list(sys.modules):
        if module_name == "backend" or module_name.startswith("backend."):
            sys.modules.pop(module_name, None)


def load_test_client(database_url: str) -> TestClient:
    os.environ["DATABASE_URL"] = database_url
    clear_backend_modules()
    backend_main = importlib.import_module("backend.main")
    return TestClient(backend_main.app)


def sample_recipe_payload(title: str = "Grilled Cheese Sandwich") -> dict:
    return {
        "title": title,
        "summary": "A quick comfort-food classic with crisp bread and melty cheese.",
        "cuisine": "American",
        "prep_time": "5 minutes",
        "cook_time": "10 minutes",
        "total_time": "15 minutes",
        "servings": "2",
        "difficulty": "Easy",
        "image_url": "https://images.example.com/grilled-cheese.jpg",
        "source_domain": "example.com",
        "ingredients": [
            {"quantity": "2", "unit": "slices", "item": "bread"},
            {"quantity": "2", "unit": "slices", "item": "cheddar"},
        ],
        "instructions": [
            "Butter the bread.",
            "Add the cheese and grill until golden.",
        ],
        "nutrition": {"calories": "420 kcal", "protein": "18 g"},
        "substitutions": [
            {
                "ingredient": "cheddar",
                "alternatives": ["mozzarella", "gouda"],
                "notes": "Use any good melting cheese.",
            }
        ],
        "shopping_list": [
            {"item": "bread", "quantity": "1 loaf", "category": "Bakery"},
            {"item": "cheddar", "quantity": "200 g", "category": "Dairy"},
        ],
        "related_recipes": ["Tomato Soup"],
    }


@dataclass
class DummyScrapedPage:
    url: str
    domain: str
    title: str | None
    description: str | None
    image_url: str | None
    raw_html: str
    text: str


class BackendEndToEndTests(unittest.TestCase):
    def setUp(self) -> None:
        if self._testMethodName == "test_startup_falls_back_to_sqlite_when_primary_database_is_unreachable":
            self.client = None
            return
        self.client = load_test_client("sqlite+pysqlite:///:memory:")
        self.client.__enter__()

    def tearDown(self) -> None:
        if self.client is not None:
            self.client.__exit__(None, None, None)
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("DATABASE_FALLBACK_ENABLED", None)
        os.environ.pop("DATABASE_FALLBACK_URL", None)
        os.environ.pop("CORS_ALLOWED_ORIGINS", None)
        os.environ.pop("CORS_ALLOWED_ORIGIN_REGEX", None)
        clear_backend_modules()

    def test_health_check_and_empty_history(self) -> None:
        health_response = self.client.get("/api/health")
        self.assertEqual(health_response.status_code, 200)
        self.assertEqual(health_response.json()["status"], "ok")

        history_response = self.client.get("/api/recipes")
        self.assertEqual(history_response.status_code, 200)
        self.assertEqual(history_response.json(), [])

    def test_extract_from_raw_text_persists_and_can_be_read_back(self) -> None:
        recipe_payload = sample_recipe_payload()

        with patch("backend.routes.recipes.extract_recipe_bundle", return_value=recipe_payload) as mocked_llm:
            extract_response = self.client.post(
                "/api/extract",
                json={"raw_text": "Title: Grilled Cheese Sandwich"},
            )

        self.assertEqual(extract_response.status_code, 201)
        body = extract_response.json()
        self.assertEqual(body["title"], recipe_payload["title"])
        self.assertFalse(body["cached"])
        mocked_llm.assert_called_once()

        history_response = self.client.get("/api/recipes")
        self.assertEqual(history_response.status_code, 200)
        history = history_response.json()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["title"], recipe_payload["title"])

        detail_response = self.client.get(f"/api/recipes/{body['id']}")
        self.assertEqual(detail_response.status_code, 200)
        detail = detail_response.json()
        self.assertEqual(detail["shopping_list"][0]["item"], "bread")
        self.assertEqual(detail["related_recipes"], ["Tomato Soup"])

    def test_extract_uses_cache_for_repeated_manual_text(self) -> None:
        recipe_payload = sample_recipe_payload()

        with patch("backend.routes.recipes.extract_recipe_bundle", return_value=recipe_payload) as mocked_llm:
            first_response = self.client.post("/api/extract", json={"raw_text": "Same recipe text"})
            second_response = self.client.post("/api/extract", json={"raw_text": "Same recipe text"})

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 201)
        self.assertFalse(first_response.json()["cached"])
        self.assertTrue(second_response.json()["cached"])
        self.assertEqual(first_response.json()["id"], second_response.json()["id"])
        mocked_llm.assert_called_once()

    def test_extract_from_url_uses_scraper_output(self) -> None:
        recipe_payload = sample_recipe_payload(title="One Pot Pasta")
        scraped_page = DummyScrapedPage(
            url="https://example.com/recipes/one-pot-pasta",
            domain="example.com",
            title="One Pot Pasta",
            description="A fast one-pot dinner with silky sauce.",
            image_url="https://images.example.com/one-pot-pasta.jpg",
            raw_html="<html></html>",
            text="Title: One Pot Pasta",
        )

        with patch("backend.routes.recipes.scrape_recipe_page", return_value=scraped_page) as mocked_scraper:
            with patch("backend.routes.recipes.extract_recipe_bundle", return_value=recipe_payload) as mocked_llm:
                response = self.client.post(
                    "/api/extract",
                    json={"url": "https://example.com/recipes/one-pot-pasta"},
                )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["title"], "One Pot Pasta")
        self.assertEqual(response.json()["image_url"], "https://images.example.com/one-pot-pasta.jpg")
        self.assertEqual(response.json()["source_domain"], "example.com")
        mocked_scraper.assert_called_once_with("https://example.com/recipes/one-pot-pasta")
        mocked_llm.assert_called_once_with("Title: One Pot Pasta")

    def test_extract_normalizes_numeric_quantities_and_nutrition_string(self) -> None:
        recipe_payload = sample_recipe_payload(title="Simple Pancakes")
        recipe_payload["ingredients"] = [
            {"quantity": 100, "unit": "g", "item": "flour"},
            {"quantity": 2, "unit": None, "item": "eggs"},
        ]
        recipe_payload["nutrition"] = (
            "61 calories, 2 grams fat, 8 grams carbohydrates, 2 grams protein, "
            "1 grams sugar, 0.5 grams fiber, 10 milligrams of sodium"
        )

        with patch("backend.routes.recipes.extract_recipe_bundle", return_value=recipe_payload):
            response = self.client.post("/api/extract", json={"raw_text": "Simple pancake recipe"})

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["ingredients"][0]["quantity"], "100")
        self.assertEqual(body["ingredients"][1]["quantity"], "2")
        self.assertEqual(body["nutrition"]["calories"], "61 calories")
        self.assertEqual(body["nutrition"]["protein"], "2 g")
        self.assertEqual(body["nutrition"]["sodium"], "10 mg")

    def test_extract_normalizes_image_aliases_into_image_url(self) -> None:
        recipe_payload = sample_recipe_payload(title="Alias Image Recipe")
        recipe_payload.pop("image_url", None)
        recipe_payload.pop("summary", None)
        recipe_payload.pop("source_domain", None)
        recipe_payload["image"] = [{"url": "https://images.example.com/alias-image.jpg"}]
        recipe_payload["description"] = "A recipe whose image arrives under an alias field."
        recipe_payload["domain"] = "alias.example.com"

        with patch("backend.routes.recipes.extract_recipe_bundle", return_value=recipe_payload):
            response = self.client.post("/api/extract", json={"raw_text": "Alias image recipe"})

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["image_url"], "https://images.example.com/alias-image.jpg")
        self.assertEqual(body["summary"], "A recipe whose image arrives under an alias field.")
        self.assertEqual(body["source_domain"], "alias.example.com")

    def test_dashboard_and_history_search_include_modern_metadata(self) -> None:
        first_recipe = sample_recipe_payload(title="Grilled Cheese Sandwich")
        first_recipe["cuisine"] = "American"
        second_recipe = sample_recipe_payload(title="Tomato Pasta")
        second_recipe["cuisine"] = "Italian"

        with patch("backend.routes.recipes.extract_recipe_bundle", side_effect=[first_recipe, second_recipe]):
            self.client.post("/api/extract", json={"raw_text": "First recipe"})
            self.client.post("/api/extract", json={"raw_text": "Second recipe"})

        dashboard_response = self.client.get("/api/dashboard")
        self.assertEqual(dashboard_response.status_code, 200)
        dashboard = dashboard_response.json()
        self.assertEqual(dashboard["total_recipes"], 2)
        self.assertGreaterEqual(dashboard["recipes_with_images"], 2)
        self.assertEqual(dashboard["latest_recipe"]["title"], "Tomato Pasta")
        self.assertTrue(any(entry["cuisine"] == "American" for entry in dashboard["top_cuisines"]))

        search_response = self.client.get("/api/recipes", params={"search": "Tomato"})
        self.assertEqual(search_response.status_code, 200)
        search_results = search_response.json()
        self.assertEqual(len(search_results), 1)
        self.assertEqual(search_results[0]["title"], "Tomato Pasta")
        self.assertIn("summary", search_results[0])
        self.assertIn("image_url", search_results[0])

    def test_extract_falls_back_to_builtin_parser_when_llm_is_unavailable(self) -> None:
        from backend.services.llm import LLMServiceError

        with patch(
            "backend.routes.recipes.extract_recipe_bundle",
            side_effect=LLMServiceError("403 PERMISSION_DENIED"),
        ):
            response = self.client.post(
                "/api/extract",
                json={
                    "raw_text": (
                        "Simple Pancakes\n"
                        "Prep time: 10 minutes\n"
                        "Cook time: 15 minutes\n"
                        "Serves: 4\n"
                        "Ingredients\n"
                        "2 cups flour\n"
                        "2 eggs\n"
                        "1 cup milk\n"
                        "Instructions\n"
                        "1. Mix the ingredients.\n"
                        "2. Cook on a hot pan."
                    )
                },
            )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["title"], "Simple Pancakes")
        self.assertEqual(body["prep_time"], "10 minutes")
        self.assertEqual(body["servings"], "4")
        self.assertGreaterEqual(len(body["ingredients"]), 2)
        self.assertGreaterEqual(len(body["instructions"]), 2)

    def test_startup_falls_back_to_sqlite_when_primary_database_is_unreachable(self) -> None:
        os.environ["DATABASE_URL"] = "postgresql://user:pass@db.example.com:5432/recipes"
        os.environ["DATABASE_FALLBACK_ENABLED"] = "true"
        os.environ["DATABASE_FALLBACK_URL"] = "sqlite+pysqlite:///:memory:"
        clear_backend_modules()

        backend_session = importlib.import_module("backend.database.session")
        backend_main = importlib.import_module("backend.main")
        original_create_all = backend_session.Base.metadata.create_all

        def flaky_create_all(*args, **kwargs):
            if not backend_session.using_fallback_database():
                raise OperationalError(
                    "SELECT 1",
                    {},
                    Exception("Network is unreachable"),
                )
            return original_create_all(*args, **kwargs)

        with patch.object(backend_session.Base.metadata, "create_all", side_effect=flaky_create_all):
            with TestClient(backend_main.app) as client:
                response = client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["database_mode"], "fallback-sqlite")

    def test_cors_allows_configured_vercel_origin(self) -> None:
        os.environ["CORS_ALLOWED_ORIGINS"] = "https://recipy-extractor-sl4n.vercel.app"
        clear_backend_modules()
        backend_main = importlib.import_module("backend.main")

        with TestClient(backend_main.app) as client:
            response = client.options(
                "/api/extract",
                headers={
                    "Origin": "https://recipy-extractor-sl4n.vercel.app",
                    "Access-Control-Request-Method": "POST",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("access-control-allow-origin"),
            "https://recipy-extractor-sl4n.vercel.app",
        )


if __name__ == "__main__":
    unittest.main()
