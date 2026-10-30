"""Gemini client for proposal interpretation; deterministic scoring stays in Python."""

from __future__ import annotations

import json
import os
from typing import Any, Mapping, Sequence

from . import config as _config  # noqa: F401 - loading .env is an intentional import side effect


class GeminiEvaluationError(RuntimeError):
    """Base class for Gemini configuration, API, and response errors."""


class GeminiConfigurationError(GeminiEvaluationError):
    pass


class MalformedLLMResponseError(GeminiEvaluationError):
    pass


class GeminiAPIError(GeminiEvaluationError):
    pass


def _criteria_payload(criteria: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "criterion_id": criterion["criterion_id"],
            "name": criterion["name"],
            "description": criterion.get("description", ""),
            "weight": criterion["weight"],
            "max_score": criterion["max_score"],
        }
        for criterion in criteria
        if bool(criterion.get("is_active", True))
    ]


_SYSTEM_PROMPT = (
    "You evaluate supplier RFP proposals against the supplied active criteria. "
    "Use only information explicitly present in the proposal. Never invent evidence, "
    "certifications, references, prices, dates, or claims. Return JSON only with fields "
    "supplier_name, criteria, risks, and overall_summary. Include exactly one criteria "
    "assessment for every supplied active criterion, with criterion_id, score, max_score, "
    "justification, and evidence. Scores must be numeric from 0 through that criterion's "
    "max_score. Evidence must be a concise quote or precise paraphrase grounded in the "
    "proposal; use an empty string when no supporting evidence exists. Do not treat the "
    "document's synthetic-data disclaimer as a business risk; preserve actual delivery, "
    "commercial, technical, privacy, and security risks. The submitted supplier name is "
    "canonical; return the supplier name stated in the proposal, but do not alter identity "
    "or metadata outside the assessment.\n\n"
    "Scoring guidance: score each criterion for requirement coverage, evidence quality, "
    "feasibility, and material gaps/risks. Proposal length or detail alone earns no points. "
    "Distinguish a supplier assertion from attached or otherwise substantiating evidence; "
    "do not describe a claim as independently verified unless the proposal supplies that "
    "evidence. For Commercial Value, assess cost clarity, scope coverage, total cost, "
    "assumptions, exclusions, and risk-adjusted value; do not infer market competitiveness "
    "without an explicit budget or comparable pricing. Use this scale: 0 = no response; "
    "1-2 = largely absent; 3-4 = major gaps; 5-6 = partial coverage; 7-8 = strong coverage "
    "with meaningful gaps; 9 = excellent coverage with only minor gaps; 10 = comprehensive "
    "coverage of every material requirement with direct, specific, credible evidence and "
    "no material unresolved gaps. Do not award 10 for proposal assertions or detail alone. "
    "Do not calculate absolute weighted scores, benchmarks, PPI, or rank."
)


def is_placeholder_setting(value: str | None) -> bool:
    """Recognize common documentation/test placeholders without revealing values."""
    if not value:
        return True
    normalized = value.strip().casefold()
    return any(marker in normalized for marker in (
        "your-", "your_", "placeholder", "dummy", "test-key", "changeme", "change-me", "<", ">"
    ))


class GeminiEvaluator:
    """Request JSON criterion assessments from Google's official Gen AI SDK."""

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        client: Any | None = None,
        timeout_seconds: float = 90,
    ) -> None:
        self.model = model or os.getenv("GEMINI_MODEL")
        if not self.model:
            raise GeminiConfigurationError("GEMINI_MODEL is not set; select a model enabled for your account")
        self.timeout_seconds = timeout_seconds
        self._injected_client = client is not None
        if client is not None:
            self.client = client
            return
        resolved_key = api_key or os.getenv("GEMINI_API_KEY")
        if not resolved_key:
            raise GeminiConfigurationError("GEMINI_API_KEY is not set")
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise GeminiConfigurationError("Install the official Gemini SDK with `pip install google-genai`") from exc
        try:
            self.client = genai.Client(
                api_key=resolved_key,
                http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000)),
            )
        except Exception as exc:
            raise GeminiConfigurationError(f"Could not initialize the Gemini client ({type(exc).__name__})") from exc

    def _generate(self, prompt: str, *, max_output_tokens: int, json_response: bool = False) -> str:
        request_config: dict[str, Any] = {
            "temperature": 0,
            "max_output_tokens": max_output_tokens,
        }
        if json_response:
            request_config["response_mime_type"] = "application/json"
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=request_config,
            )
        except Exception as exc:
            code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
            kind = type(exc).__name__.casefold()
            if code == 429:
                hint = "rate limit or quota reached; check Google AI Studio usage and retry later"
            elif code in (401, 403):
                hint = "authentication or API access failed; verify the key and project access"
            elif code == 404:
                hint = "model not found; verify GEMINI_MODEL is an available model ID"
            elif code in (500, 502, 503, 504):
                hint = "service is temporarily unavailable; retry later"
            elif code == 400:
                hint = "Gemini rejected the request; verify the selected model and request configuration"
            elif "timeout" in kind:
                hint = "request timed out; retry or increase the configured timeout"
            else:
                hint = "request failed; verify network, key, model access, and quota"
            suffix = f" (HTTP {code})" if isinstance(code, int) else ""
            raise GeminiAPIError(f"Gemini {hint}{suffix}. Error type: {type(exc).__name__}.") from exc
        text = getattr(response, "text", None)
        if not isinstance(text, str) or not text.strip():
            raise MalformedLLMResponseError("Gemini returned an empty or non-text response")
        return text.strip()

    def evaluate(self, proposal_text: str, criteria: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        active = _criteria_payload(criteria)
        if not active:
            raise GeminiConfigurationError("At least one active criterion is required")
        request = json.dumps(
            {"active_criteria": active, "proposal_text": proposal_text},
            ensure_ascii=False,
        )
        response_text = self._generate(
            f"{_SYSTEM_PROMPT}\n\nEvaluate this proposal and return JSON only:\n{request}",
            max_output_tokens=4096,
            json_response=True,
        )
        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise MalformedLLMResponseError(f"Gemini returned malformed JSON: {exc.msg}") from exc
        if not isinstance(parsed, dict):
            raise MalformedLLMResponseError("Gemini response must be a JSON object")
        return parsed

    def smoke_test(self) -> None:
        """Make one minimal, non-sensitive request and reject empty responses."""
        self._generate("Reply with the single word OK.", max_output_tokens=8)

    def close(self) -> None:
        if not self._injected_client and hasattr(self.client, "close"):
            self.client.close()
