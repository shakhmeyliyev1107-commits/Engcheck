"""Testlar uchun soxta provayder: tarmoqsiz, oldindan belgilangan javoblar bilan."""
from engcheck.ai.base import AiError, ChatResult, Provider


class FakeProvider(Provider):
    kind = "fake"

    def __init__(self, name="soxta", base_url="http://127.0.0.1:9", replies=None, fail=None, vectors=None):
        super().__init__(name, "fake-model", base_url, "fake-embed" if vectors is not None else None)
        self.replies = list(replies or [])
        self.fail = fail            # AiError kodi: ping va chat shu xato bilan yiqiladi
        self.vectors = vectors      # callable(text) -> list[float]
        self.calls: list[tuple[str, str]] = []

    def chat(self, system, user, max_tokens=4000):
        if self.fail:
            raise AiError(self.fail)
        self.calls.append((system, user))
        reply = self.replies.pop(0) if self.replies else "{}"
        if isinstance(reply, Exception):
            raise reply
        return ChatResult(reply, self.model)

    def embed(self, texts):
        if self.vectors is None:
            raise AiError("embeddings_unsupported")
        return [self.vectors(t) for t in texts]

    def ping(self):
        if self.fail:
            raise AiError(self.fail)
