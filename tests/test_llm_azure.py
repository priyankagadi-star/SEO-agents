"""AzureOpenAIClient adapter — pinned against a mocked Responses API."""
import json

import httpx
import pytest

from llm import AzureOpenAIClient

ENDPOINT = "https://res.cognitiveservices.azure.com/openai/responses?api-version=2025-04-01-preview"


def respond_with(payload, capture):
    def handler(request: httpx.Request) -> httpx.Response:
        capture.append(request)
        return httpx.Response(200, json=payload)
    return httpx.MockTransport(handler)


def make_client(payload, capture, **kw):
    return AzureOpenAIClient(
        endpoint=ENDPOINT, api_key="test-key",
        deployments={"strong": "gpt-strong", "fast": "gpt-fast"},
        transport=respond_with(payload, capture), **kw)


GOOD = {
    "status": "completed",
    "output": [
        {"type": "reasoning", "content": []},
        {"type": "message", "content": [
            {"type": "output_text", "text": '{"lead": "An answer-first lead."}'},
        ]},
    ],
    "usage": {"input_tokens": 321, "output_tokens": 45},
}


def test_complete_parses_text_and_usage():
    seen = []
    text, usage = make_client(GOOD, seen).complete("prompt text", "fast")
    assert json.loads(text)["lead"] == "An answer-first lead."
    assert usage == {"model": "azure:gpt-fast", "input_tokens": 321, "output_tokens": 45}
    req = seen[0]
    assert req.headers["api-key"] == "test-key"
    body = json.loads(req.content)
    assert body["model"] == "gpt-fast" and body["input"] == "prompt text"


def test_tier_maps_to_deployment():
    seen = []
    make_client(GOOD, seen).complete("p", "strong")
    assert json.loads(seen[0].content)["model"] == "gpt-strong"


def test_fallback_deployment_env(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-shared")
    seen = []
    client = AzureOpenAIClient(endpoint=ENDPOINT, api_key="k", deployments={},
                               transport=respond_with(GOOD, seen))
    client.complete("p", "strong")
    assert json.loads(seen[0].content)["model"] == "gpt-shared"


def test_missing_deployment_is_loud(monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT", raising=False)
    client = AzureOpenAIClient(endpoint=ENDPOINT, api_key="k", deployments={})
    with pytest.raises(RuntimeError, match="deployment"):
        client.complete("p", "strong")


def test_missing_credentials_is_loud(monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="AZURE_OPENAI_ENDPOINT"):
        AzureOpenAIClient()


def test_incomplete_status_raises():
    bad = {"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"},
           "output": [], "usage": {}}
    with pytest.raises(RuntimeError, match="not completed"):
        make_client(bad, []).complete("p", "fast")


def test_http_error_raises():
    def handler(request):
        return httpx.Response(401, json={"error": {"message": "bad key"}})
    client = AzureOpenAIClient(endpoint=ENDPOINT, api_key="wrong",
                               deployments={"fast": "d"},
                               transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        client.complete("p", "fast")
