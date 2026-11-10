import json

import httpx
import httpx2
import pytest
from anthropic import DefaultHttpxClient

from engcheck.ai.anthropic_provider import AnthropicProvider
from engcheck.ai.base import AiError, is_local_url
from engcheck.ai.ollama import OllamaProvider
from engcheck.ai.openai_compat import OpenAICompatProvider


@pytest.mark.parametrize("url,local", [
    ("http://127.0.0.1:11434", True), ("http://localhost:1234/v1", True), ("http://[::1]:8080", True),
    ("http://192.168.1.20:8000/v1", True), ("http://10.0.0.5", True),
    ("https://api.openai.com/v1", False), ("https://api.anthropic.com", False),
    ("http://llm.corp.example", False), ("http://8.8.8.8", False), (None, False), ("", False),
])
def test_is_local_url(url, local):
    assert is_local_url(url) is local


# ---------- Anthropic (rasmiy SDK, soxta transport) ----------
def _message(text="Salom", stop_reason="end_turn"):
    return {"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [{"type": "thinking", "thinking": "", "signature": "s"}, {"type": "text", "text": text}],
            "stop_reason": stop_reason, "stop_sequence": None,
            "usage": {"input_tokens": 3, "output_tokens": 2}}


def _anthropic(handler, model="claude-opus-5-5"):
    seen = []

    def wrapped(request):
        seen.append(request)
        return handler(request)
    client = DefaultHttpxClient(transport=httpx2.MockTransport(wrapped))
    return AnthropicProvider("claude", model, api_key="sk-ant-test", http_client=client), seen


def test_anthropic_chat_request_shape():
    p, seen = _anthropic(lambda r: httpx2.Response(200, json=_message("Javob")))
    res = p.chat("Sen muhandissan", "V-101 ni tekshir")
    assert res.text == "Javob" and res.model == "claude-opus-5-5"
    req = seen[0]
    body = json.loads(req.content)
    assert str(req.url) == "https://api.anthropic.com/v1/messages"      # muhit o'zgaruvchisidan olinmaydi
    auth = req.headers.get("x-api-key") or req.headers.get("authorization", "")
    assert auth.endswith("sk-ant-test")
    assert body["model"] == "claude-opus-5-5" and body["system"] == "Sen muhandissan"
    assert body["messages"] == [{"role": "user", "content": "V-101 ni tekshir"}]
    assert body["thinking"] == {"type": "adaptive"} and body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in req.headers["anthropic-beta"]
    assert "temperature" not in body and p.is_local is False


def test_anthropic_unknown_model_sends_no_model_gated_params():
    p, seen = _anthropic(lambda r: httpx2.Response(200, json=_message()), model="some-future-model")
    p.chat("s", "u")
    body = json.loads(seen[0].content)
    assert "thinking" not in body and "fallbacks" not in body


def test_anthropic_refusal_is_reported_not_returned_as_text():
    p, _ = _anthropic(lambda r: httpx2.Response(200, json=_message("", "refusal")))
    with pytest.raises(AiError) as e:
        p.chat("s", "u")
    assert e.value.code == "refused"


@pytest.mark.parametrize("status,code", [(401, "auth"), (403, "auth"), (429, "rate_limit"), (400, "bad_request"),
                                         (404, "bad_request"), (529, "server"), (500, "server")])
def test_anthropic_error_mapping(status, code):
    err = {"type": "error", "error": {"type": "x", "message": "sk-ant-test leaked?"}}
    p, _ = _anthropic(lambda r: httpx2.Response(status, json=err))
    with pytest.raises(AiError) as e:
        p.chat("s", "u")
    assert e.value.code == code and "sk-ant-test" not in str(e.value)


def test_anthropic_network_failure_is_unreachable():
    def boom(request):
        raise httpx2.ConnectError("no route")
    p, _ = _anthropic(boom)
    with pytest.raises(AiError) as e:
        p.chat("s", "u")
    assert e.value.code == "unreachable"


def test_anthropic_ping_uses_models_api_and_has_no_embeddings():
    p, seen = _anthropic(lambda r: httpx2.Response(200, json={
        "id": "claude-opus-5-5", "type": "model", "display_name": "Claude Opus 5.5", "created_at": "2026-01-01T00:00:00Z"}))
    p.ping()
    assert seen[0].url.path == "/v1/models/claude-opus-5-5"
    with pytest.raises(AiError) as e:
        p.embed(["a"])
    assert e.value.code == "embeddings_unsupported"


# ---------- OpenAI-mos ----------
def _openai(handler, **kw):
    seen = []

    def wrapped(request):
        seen.append(request)
        return handler(request)
    kw.setdefault("api_key", "sk-oa")
    return OpenAICompatProvider("oa", "https://api.example.com/v1", "gpt-x", transport=httpx.MockTransport(wrapped), **kw), seen


def test_openai_chat_and_embed_shapes():
    def handler(r):
        if r.url.path.endswith("/chat/completions"):
            return httpx.Response(200, json={"model": "gpt-x-0613", "choices": [{"message": {"content": "Javob"}}]})
        return httpx.Response(200, json={"data": [{"index": 1, "embedding": [0, 1]}, {"index": 0, "embedding": [1, 0]}]})
    p, seen = _openai(handler, embed_model="emb-1")
    assert p.chat("sys", "user", max_tokens=500).text == "Javob"
    body = json.loads(seen[0].content)
    assert str(seen[0].url) == "https://api.example.com/v1/chat/completions"
    assert seen[0].headers["authorization"] == "Bearer sk-oa"
    assert body == {"model": "gpt-x", "max_tokens": 500,
                    "messages": [{"role": "system", "content": "sys"}, {"role": "user", "content": "user"}]}
    assert p.embed(["a", "b"]) == [[1, 0], [0, 1]]           # index bo'yicha tartiblanadi
    assert json.loads(seen[1].content) == {"model": "emb-1", "input": ["a", "b"]}


def test_openai_without_key_sends_no_auth_header_and_is_local_by_url():
    seen = []
    p = OpenAICompatProvider("lm", "http://127.0.0.1:1234/v1/", "local-model", api_key=None,
                             transport=httpx.MockTransport(lambda r: (seen.append(r), httpx.Response(200, json={"data": []}))[1]))
    p.ping()
    assert "authorization" not in seen[0].headers and str(seen[0].url) == "http://127.0.0.1:1234/v1/models"
    assert p.is_local is True


def test_openai_embeddings_need_embed_model():
    p, _ = _openai(lambda r: httpx.Response(200, json={}))
    with pytest.raises(AiError) as e:
        p.embed(["a"])
    assert e.value.code == "embeddings_unsupported"


@pytest.mark.parametrize("status,code", [(401, "auth"), (429, "rate_limit"), (404, "bad_request"), (503, "server")])
def test_openai_error_mapping(status, code):
    p, _ = _openai(lambda r: httpx.Response(status, text="Incorrect API key provided: sk-oa"))
    with pytest.raises(AiError) as e:
        p.chat("s", "u")
    assert e.value.code == code and "sk-oa" not in str(e.value)


def test_openai_unreachable_and_malformed_body():
    def boom(r):
        raise httpx.ConnectError("refused")
    p, _ = _openai(boom)
    with pytest.raises(AiError) as e:
        p.ping()
    assert e.value.code == "unreachable"
    p, _ = _openai(lambda r: httpx.Response(200, text="<html>proxy</html>"))
    with pytest.raises(AiError) as e:
        p.chat("s", "u")
    assert e.value.code == "server"


# ---------- Ollama ----------
def test_ollama_shapes():
    seen = []

    def handler(r):
        seen.append(r)
        if r.url.path == "/api/chat":
            return httpx.Response(200, json={"model": "llama3", "message": {"role": "assistant", "content": "Javob"}})
        if r.url.path == "/api/embed":
            return httpx.Response(200, json={"embeddings": [[0.1, 0.2]]})
        return httpx.Response(200, json={"models": []})
    p = OllamaProvider("lokal", "http://127.0.0.1:11434", "llama3", embed_model="nomic", transport=httpx.MockTransport(handler))
    assert p.is_local and p.chat("sys", "user", max_tokens=300).text == "Javob"
    body = json.loads(seen[0].content)
    assert body["stream"] is False and body["model"] == "llama3" and body["options"] == {"num_predict": 300}
    assert body["messages"][0] == {"role": "system", "content": "sys"}
    assert p.embed(["a"]) == [[0.1, 0.2]] and json.loads(seen[1].content) == {"model": "nomic", "input": ["a"]}
    p.ping()
    assert seen[2].url.path == "/api/tags"


def test_ollama_missing_model_is_bad_request():
    p = OllamaProvider("lokal", "http://127.0.0.1:11434", "nope",
                       transport=httpx.MockTransport(lambda r: httpx.Response(404, json={"error": "model not found"})))
    with pytest.raises(AiError) as e:
        p.chat("s", "u")
    assert e.value.code == "bad_request"
