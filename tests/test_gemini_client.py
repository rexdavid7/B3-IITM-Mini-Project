import json
from types import SimpleNamespace

import pytest

from rfp_eval.gemini_client import (
    GeminiAPIError,
    GeminiConfigurationError,
    GeminiEvaluator,
    MalformedLLMResponseError,
)


CRITERIA = [{"criterion_id": 8, "name": "Cost", "description": "Value", "weight": 100, "max_score": 5, "is_active": 1}]


class FakeGeminiClient:
    def __init__(self, text=None, error=None):
        self.text = text
        self.error = error
        self.call = None
        self.models = self

    def generate_content(self, **kwargs):
        self.call = kwargs
        if self.error:
            raise self.error
        return SimpleNamespace(text=self.text)


def test_evaluation_uses_selected_model_and_json_prompt():
    answer = {"supplier_name": "A", "criteria": [], "risks": [], "overall_summary": ""}
    client = FakeGeminiClient(json.dumps(answer))
    evaluator = GeminiEvaluator(client=client, model="account-selected-model")
    assert evaluator.evaluate("Proposal says 5 dollars", CRITERIA) == answer
    assert client.call["model"] == "account-selected-model"
    assert client.call["config"]["response_mime_type"] == "application/json"
    assert client.call["config"]["max_output_tokens"] == 4096
    assert "Never invent evidence" in client.call["contents"]
    assert "proposal length or detail alone earns no points" in client.call["contents"].casefold()
    assert "no material unresolved gaps" in client.call["contents"].casefold()
    assert "do not infer market competitiveness" in client.call["contents"].casefold()
    assert '"criterion_id": 8' in client.call["contents"]
    assert '"proposal_text": "Proposal says 5 dollars"' in client.call["contents"]


def test_smoke_test_makes_one_minimal_request():
    client = FakeGeminiClient("OK")
    GeminiEvaluator(client=client, model="selected-model").smoke_test()
    assert client.call["model"] == "selected-model"
    assert client.call["config"]["max_output_tokens"] == 8
    assert "response_mime_type" not in client.call["config"]
    assert "OK" in client.call["contents"]


def test_malformed_json_and_empty_responses_are_reported():
    with pytest.raises(MalformedLLMResponseError, match="malformed JSON"):
        GeminiEvaluator(client=FakeGeminiClient("not json"), model="test-model").evaluate("text", CRITERIA)
    with pytest.raises(MalformedLLMResponseError, match="empty"):
        GeminiEvaluator(client=FakeGeminiClient(""), model="test-model").smoke_test()


@pytest.mark.parametrize(
    "code, phrase",
    [
        (429, "rate limit"),
        (403, "authentication or API access"),
        (404, "model not found"),
        (503, "temporarily unavailable"),
    ],
)
def test_api_failures_have_safe_diagnostic_hints(code, phrase):
    error = RuntimeError("provider details must not be echoed")
    error.code = code
    with pytest.raises(GeminiAPIError, match=phrase) as caught:
        GeminiEvaluator(client=FakeGeminiClient(error=error), model="test-model").smoke_test()
    assert "provider details must not be echoed" not in str(caught.value)


def test_timeout_is_reported_safely():
    with pytest.raises(GeminiAPIError, match="timed out"):
        GeminiEvaluator(client=FakeGeminiClient(error=TimeoutError()), model="test-model").smoke_test()


def test_api_key_and_model_are_required_without_printing_credentials(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_MODEL", "test-model")
    with pytest.raises(GeminiConfigurationError, match="GEMINI_API_KEY"):
        GeminiEvaluator()
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-value")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    with pytest.raises(GeminiConfigurationError, match="GEMINI_MODEL"):
        GeminiEvaluator()


def test_key_is_read_from_environment_without_overriding_model_argument(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-value")
    evaluator = GeminiEvaluator(client=FakeGeminiClient(), model="configured-model")
    assert evaluator.model == "configured-model"
