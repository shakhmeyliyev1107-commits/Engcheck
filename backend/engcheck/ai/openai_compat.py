"""OpenAI protokoliga mos har qanday xizmat (OpenAI, OpenRouter, vLLM, LM Studio va h.k.)."""
import httpx

from .base import AiError, ChatResult, Provider, is_local_url, status_to_code


class HttpProvider(Provider):
    """HTTP orqali ishlaydigan provayderlar uchun umumiy qism."""

    def __init__(self, name, base_url, model, embed_model=None, api_key=None, transport=None):
        super().__init__(name, model, (base_url or "").rstrip("/"), embed_model)
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        # Lokal provayder muhitdagi proksi (HTTP(S)_PROXY) orqali chiqmaydi; yo'naltirishga ergashilmaydi.
        self._http = httpx.Client(headers=headers, transport=transport, timeout=httpx.Timeout(180.0, connect=5.0),
                                  trust_env=not is_local_url(self.base_url), follow_redirects=False)

    def _request(self, method: str, path: str, payload: dict | None = None, timeout: float | None = None) -> dict:
        try:
            kwargs = {"timeout": timeout} if timeout else {}
            response = self._http.request(method, f"{self.base_url}{path}", json=payload, **kwargs)
        except httpx.HTTPError as exc:
            raise AiError("unreachable") from exc
        if response.status_code >= 400:
            raise AiError(status_to_code(response.status_code))
        try:
            data = response.json()
        except ValueError as exc:
            raise AiError("server") from exc
        if not isinstance(data, dict):
            raise AiError("server")
        return data


class OpenAICompatProvider(HttpProvider):
    kind = "openai_compatible"

    def chat(self, system: str, user: str, max_tokens: int = 4000) -> ChatResult:
        data = self._request("POST", "/chat/completions", {
            "model": self.model, "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise AiError("server") from exc
        return ChatResult(text=text, model=data.get("model") or self.model)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.embed_model:
            raise AiError("embeddings_unsupported")
        data = self._request("POST", "/embeddings", {"model": self.embed_model, "input": texts})
        try:
            rows = sorted(data["data"], key=lambda r: r.get("index", 0))
            return [row["embedding"] for row in rows]
        except (KeyError, TypeError) as exc:
            raise AiError("server") from exc

    def ping(self) -> None:
        self._request("GET", "/models", timeout=5.0)
