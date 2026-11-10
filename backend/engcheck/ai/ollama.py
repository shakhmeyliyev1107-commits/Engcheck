"""Ollama — lokal modellar (oflayn rejim)."""
from .base import AiError, ChatResult
from .openai_compat import HttpProvider

DEFAULT_URL = "http://127.0.0.1:11434"


class OllamaProvider(HttpProvider):
    kind = "ollama"

    def __init__(self, name, base_url, model, embed_model=None, api_key=None, transport=None):
        super().__init__(name, base_url or DEFAULT_URL, model, embed_model, api_key, transport)

    def chat(self, system: str, user: str, max_tokens: int = 4000) -> ChatResult:
        data = self._request("POST", "/api/chat", {
            "model": self.model, "stream": False, "options": {"num_predict": max_tokens},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        try:
            return ChatResult(text=data["message"]["content"] or "", model=data.get("model") or self.model)
        except (KeyError, TypeError) as exc:
            raise AiError("server") from exc

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.embed_model:
            raise AiError("embeddings_unsupported")
        data = self._request("POST", "/api/embed", {"model": self.embed_model, "input": texts})
        if not isinstance(data.get("embeddings"), list):
            raise AiError("server")
        return data["embeddings"]

    def ping(self) -> None:
        self._request("GET", "/api/tags", timeout=5.0)
