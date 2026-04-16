from __future__ import annotations

import importlib
import unittest
from types import SimpleNamespace
from unittest.mock import patch

class DummyResponse:
    def __init__(self, content):
        self.content = content


class LLMServiceTests(unittest.TestCase):
    def test_detects_temporary_unavailable_error(self) -> None:
        llm = importlib.import_module("backend.services.llm")
        error = Exception("503 UNAVAILABLE: model is experiencing high demand")
        self.assertTrue(llm.is_model_temporarily_unavailable(error))
        self.assertFalse(llm.is_model_permission_error(error))

    def test_detects_permission_error(self) -> None:
        llm = importlib.import_module("backend.services.llm")
        error = Exception("403 PERMISSION_DENIED. Your API key was reported as leaked.")
        self.assertTrue(llm.is_model_permission_error(error))
        self.assertFalse(llm.is_model_temporarily_unavailable(error))

    def test_detects_quota_error_and_retry_delay(self) -> None:
        llm = importlib.import_module("backend.services.llm")
        error = Exception(
            "429 RESOURCE_EXHAUSTED. Quota exceeded. Please retry in 33.488487903s."
        )
        self.assertTrue(llm.is_model_quota_error(error))
        self.assertEqual(llm.extract_retry_after_seconds(error), 34)

    @patch("backend.services.llm.sleep_for_retry")
    @patch("backend.services.llm.build_model")
    @patch(
        "backend.services.llm.get_settings",
        return_value=SimpleNamespace(llm_max_retries=3, llm_unavailable_retries=6, llm_retry_backoff_seconds=0),
    )
    def test_retries_unavailable_errors_before_succeeding(self, _settings, mock_build_model, _sleep) -> None:
        llm = importlib.import_module("backend.services.llm")
        model = mock_build_model.return_value
        model.invoke.side_effect = [
            Exception("503 UNAVAILABLE: high demand"),
            DummyResponse('{"title":"Soup","ingredients":[],"instructions":[],"substitutions":[],"shopping_list":[],"related_recipes":[]}'),
        ]

        result = llm.invoke_with_model("prompt", "gemini-2.5-flash")

        self.assertEqual(result["title"], "Soup")
        self.assertEqual(model.invoke.call_count, 2)

    @patch("backend.services.llm.sleep_for_retry")
    @patch("backend.services.llm.build_model")
    @patch(
        "backend.services.llm.get_settings",
        return_value=SimpleNamespace(llm_max_retries=3, llm_unavailable_retries=4, llm_retry_backoff_seconds=0),
    )
    def test_raises_temporary_error_after_unavailable_retries(self, _settings, mock_build_model, _sleep) -> None:
        llm = importlib.import_module("backend.services.llm")
        model = mock_build_model.return_value
        model.invoke.side_effect = Exception("503 UNAVAILABLE: high demand")

        with self.assertRaises(llm.LLMTemporaryServiceError):
            llm.invoke_with_model("prompt", "gemini-2.5-flash")

    @patch("backend.services.llm.invoke_with_model")
    @patch(
        "backend.services.llm.get_settings",
        return_value=SimpleNamespace(gemini_model="gemini-2.5-flash", gemini_fallback_model="gemini-1.5-flash"),
    )
    @patch("backend.services.llm.load_prompt", return_value='{"recipe":"{recipe_text}"}')
    def test_uses_fallback_model_after_temporary_primary_failure(
        self, _load_prompt, _settings, mock_invoke_with_model
    ) -> None:
        llm = importlib.import_module("backend.services.llm")
        mock_invoke_with_model.side_effect = [
            llm.LLMTemporaryServiceError("temporary failure"),
            {"title": "Soup"},
        ]

        result = llm.invoke_json_prompt("recipe_extraction.txt", recipe_text="Soup")

        self.assertEqual(result["title"], "Soup")
        self.assertEqual(mock_invoke_with_model.call_args_list[0].args[1], "gemini-2.5-flash")
        self.assertEqual(mock_invoke_with_model.call_args_list[1].args[1], "gemini-1.5-flash")

    @patch(
        "backend.services.llm.get_settings",
        return_value=SimpleNamespace(llm_best_effort_enrichment=True),
    )
    @patch("backend.services.llm.invoke_json_prompt")
    def test_best_effort_enrichment_skips_temporary_failures(self, mock_invoke_json_prompt, _settings) -> None:
        llm = importlib.import_module("backend.services.llm")
        mock_invoke_json_prompt.side_effect = llm.LLMQuotaExceededError(
            "Gemini quota is exhausted for model 'gemini-2.5-flash'.",
            retry_after_seconds=34,
        )

        result = llm.invoke_optional_json_prompt("nutrition.txt", recipe_json="{}")

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
