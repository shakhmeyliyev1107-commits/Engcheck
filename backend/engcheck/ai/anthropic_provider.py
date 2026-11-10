"""Claude — rasmiy Anthropic SDK orqali."""
import anthropic

from .base import AiError, ChatResult, Provider, status_to_code

DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_URL = "https://api.anthropic.com"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Adaptiv fikrlashni qabul qiladigan modellar oilalari.
_ADAPTIVE = ("claude-opus-5", "claude-opus-4-8", "claude-opus-4-7", "claude-opus-4-6", "claude-sonnet-5",
             "claude-sonnet-4-6", "claude-haiku-5", "claude-fable-5", "claude-mythos-5")
# Xavfsizlik klassifikatori rad etganda server tomonida zaxira modelga o'tishni qo'llaydigan modellar.
_FALLBACKS = ("claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-1", "claude-fable-5-2")


class AnthropicProvider(Provider):
    kind = "anthropic"

    def __init__(self, name: str, model: str | None, api_key: str | None, base_url: str | None = None,
                 http_client=None):
        super().__init__(name, model or DEFAULT_MODEL, base_url)
        self._client = anthropic.Anthropic(api_key=api_key or "missing", base_url=base_url or DEFAULT_URL,   # aniq manzil: ANTHROPIC_BASE_URL muhitidan olinmaydi
                                          
                                           timeout=180.0, max_retries=1, http_client=http_client)

    @property
    def is_local(self) -> bool:
        return False if not self.base_url else super().is_local

    def _call(self, fn):
        try:
            return fn()
        except anthropic.APIConnectionError as exc:   # tarmoq xatosi va taymaut
            raise AiError("unreachable") from exc
        except anthropic.APIStatusError as exc:
            raise AiError(status_to_code(exc.status_code)) from exc

    def chat(self, system: str, user: str, max_tokens: int = 16000) -> ChatResult:
        params: dict = {"model": self.model, "max_tokens": max_tokens, "system": system,
                        "messages": [{"role": "user", "content": user}]}
        if self.model.startswith(_ADAPTIVE):
            params["thinking"] = {"type": "adaptive"}
        if self.model.startswith(_FALLBACKS):
            params["betas"] = [FALLBACK_BETA]
            params["fallbacks"] = "default"
            response = self._call(lambda: self._client.beta.messages.create(**params))
        else:
            response = self._call(lambda: self._client.messages.create(**params))
        if response.stop_reason == "refusal":
            raise AiError("refused")
        text = "".join(block.text for block in response.content if block.type == "text")
        return ChatResult(text=text, model=response.model)

    def ping(self) -> None:
        self._call(lambda: self._client.models.retrieve(self.model))
