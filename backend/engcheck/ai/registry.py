"""Provayderni qurish va joriy rejimni (online / local / none) tanlash."""
from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session as Db

from ..core.models import AiProvider, Project
from ..core.secrets import SecretStore
from .anthropic_provider import AnthropicProvider
from .base import AiError, Provider
from .ollama import OllamaProvider
from .openai_compat import OpenAICompatProvider

KINDS = ("anthropic", "openai_compatible", "ollama")


def secret_name(provider_id: int) -> str:
    return f"ai_provider:{provider_id}"


def build(row: AiProvider, key: str | None) -> Provider:
    if row.kind == "anthropic":
        return AnthropicProvider(row.name, row.model, key, row.base_url)
    if row.kind == "openai_compatible":
        return OpenAICompatProvider(row.name, row.base_url, row.model, row.embed_model, key)
    if row.kind == "ollama":
        return OllamaProvider(row.name, row.base_url, row.model, row.embed_model, key)
    raise ValueError(f"noma'lum provayder turi: {row.kind}")


@dataclass
class Resolution:
    provider: Provider | None
    mode: str                 # online | local | none
    reason: str | None = None  # none bo'lsa sabab: no_provider | cloud_not_allowed | AiError kodi


def resolve(db: Db, store: SecretStore, project: Project | None,
            factory: Callable[[AiProvider, str | None], Provider] = build,
            allow_cloud: bool | None = None) -> Resolution:
    """Birinchi yaroqli provayderni tanlaydi: standart provayder, keyin qolganlari.

    Bulutli provayder faqat loyiha ruxsat bersa ishlatiladi. Javob bermagan provayder
    o'tkazib yuboriladi — internet yo'q bo'lsa lokal modelga o'tiladi.
    """
    if allow_cloud is None:
        allow_cloud = bool(project and project.allow_cloud_ai)
    rows = (db.query(AiProvider).filter_by(enabled=True)
            .order_by(AiProvider.is_default.desc(), AiProvider.id).all())
    reason = None
    for row in rows:
        try:
            provider = factory(row, store.get(secret_name(row.id)))
        except ValueError:
            continue
        if not provider.is_local and not allow_cloud:
            reason = reason or "cloud_not_allowed"
            continue
        try:
            provider.ping()
        except AiError as exc:
            # Standart (birinchi) provayderning sababi eng foydali: foydalanuvchi aynan uni kutgan.
            if reason in (None, "cloud_not_allowed"):
                reason = exc.code
            continue
        return Resolution(provider, "local" if provider.is_local else "online")
    return Resolution(None, "none", reason or "no_provider")
