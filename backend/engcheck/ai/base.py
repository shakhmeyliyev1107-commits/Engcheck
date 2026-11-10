"""AI provayderlar uchun yagona interfeys."""
import ipaddress
from dataclasses import dataclass
from urllib.parse import urlparse


class AiError(Exception):
    """code: auth | rate_limit | unreachable | bad_request | refused | server | embeddings_unsupported

    Xabar matniga provayder javobi KIRITILMAYDI: unda API kaliti aks etishi mumkin.
    """

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass
class ChatResult:
    text: str
    model: str


def is_local_url(url: str | None) -> bool:
    """Manzil shu kompyuter yoki xususiy tarmoqdami. Foydalanuvchi belgilamaydi — manzildan aniqlanadi."""
    host = (urlparse(url or "").hostname or "").lower()
    if not host:
        return False
    if host == "localhost":
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False   # nomli xost: tashqi deb hisoblanadi
    return ip.is_loopback or ip.is_private


class Provider:
    kind = ""

    def __init__(self, name: str, model: str, base_url: str | None = None, embed_model: str | None = None):
        self.name, self.model, self.base_url, self.embed_model = name, model, base_url, embed_model

    @property
    def is_local(self) -> bool:
        return is_local_url(self.base_url)

    def chat(self, system: str, user: str, max_tokens: int = 4000) -> ChatResult:
        raise NotImplementedError

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise AiError("embeddings_unsupported")

    def ping(self) -> None:
        """Provayderga ulanib bo'lishini tekshiradi; bo'lmasa AiError."""
        raise NotImplementedError


def status_to_code(status: int) -> str:
    if status in (401, 403):
        return "auth"
    if status == 429:
        return "rate_limit"
    if status >= 500:
        return "server"
    return "bad_request"
