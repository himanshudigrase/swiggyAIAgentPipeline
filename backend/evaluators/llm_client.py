"""
LLM Client abstraction layer.

Supports:
- Google Gemini (default, free tier)
- OpenAI (optional override)
- Mock mode (no API key needed — for testing)

Why an abstraction layer?
- Swapping from Gemini to OpenAI is a 1-line config change
- Mock mode makes development and CI fast and free
- Consistent interface for all evaluators and the suggestion engine
"""

import json
import re
from typing import Any, Dict
from config import settings


class MockLLMClient:
    """Returns realistic mock responses. No API key required."""

    def evaluate(self, prompt: str, expect_json: bool = False) -> Dict[str, Any]:
        if expect_json:
            return {
                "_mock": True,
                "overall_score": 0.85,
                "response_quality": 0.88,
                "helpfulness": 0.87,
                "factuality": 0.90,
                "coherence_score": 0.85,
                "context_maintained": True,
                "contradictions_found": False,
                "reference_resolution_ok": True,
                "issues": [],
                "reasoning": "Mock evaluation — enable LLM_MOCK_MODE=false and set GEMINI_API_KEY for real evaluation.",
            }
        return {"_mock": True, "text": "Mock LLM response. Set LLM_MOCK_MODE=false for real evaluation."}

    def generate(self, prompt: str) -> str:
        return "Mock suggestion. Set LLM_MOCK_MODE=false and configure GEMINI_API_KEY for real suggestions."


class GeminiClient:
    """Google Gemini client using gemini-1.5-flash (free tier)."""

    def __init__(self):
        import google.generativeai as genai
        genai.configure(api_key=settings.gemini_api_key)
        self._model = genai.GenerativeModel(settings.llm_model)

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON from LLM response (handles markdown code blocks)."""
        # Strip markdown code fences if present
        text = re.sub(r"```(?:json)?\s*", "", text).strip()
        text = re.sub(r"```\s*$", "", text).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Fallback: return raw text under a key
            return {"_parse_error": True, "raw": text}

    def evaluate(self, prompt: str, expect_json: bool = False) -> Dict[str, Any]:
        try:
            response = self._model.generate_content(prompt)
            text = response.text
            if expect_json:
                return self._parse_json(text)
            return {"text": text}
        except Exception as e:
            return {"_error": str(e)}

    def generate(self, prompt: str) -> str:
        try:
            response = self._model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"LLM generation error: {e}"


class OpenAIClient:
    """OpenAI client (optional override)."""

    def __init__(self):
        from openai import OpenAI
        self._client = OpenAI(api_key=settings.openai_api_key)

    def _parse_json(self, text: str) -> Dict[str, Any]:
        text = re.sub(r"```(?:json)?\s*", "", text).strip()
        text = re.sub(r"```\s*$", "", text).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"_parse_error": True, "raw": text}

    def evaluate(self, prompt: str, expect_json: bool = False) -> Dict[str, Any]:
        try:
            resp = self._client.chat.completions.create(
                model=settings.llm_model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"} if expect_json else None,
            )
            text = resp.choices[0].message.content
            if expect_json:
                return self._parse_json(text)
            return {"text": text}
        except Exception as e:
            return {"_error": str(e)}

    def generate(self, prompt: str) -> str:
        try:
            resp = self._client.chat.completions.create(
                model=settings.llm_model,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content
        except Exception as e:
            return f"LLM generation error: {e}"


def get_llm_client():
    """Factory function — returns the appropriate LLM client based on config."""
    if settings.llm_mock_mode:
        return MockLLMClient()
    if settings.llm_provider == "openai" and settings.openai_api_key:
        return OpenAIClient()
    if settings.gemini_api_key:
        return GeminiClient()
    # Fallback to mock if no keys configured
    return MockLLMClient()
