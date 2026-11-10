"""API kalitlari ombori.

OS kalit ombori (keyring) ishlasa — o'sha yerda. Aks holda shifrlangan fayl:
`secrets.enc` (Fernet) va alohida `secret.key`, ikkalasi faqat egasi o'qiy oladigan (0600).
Fayl varianti bazaning nusxasi yoki zaxirasi tarqalganda kalitlarni himoya qiladi;
ma'lumotlar papkasiga to'liq kira olgan odamdan himoya qilmaydi.
"""
import json
import os
import threading
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

SERVICE = "engcheck"
_KEY_LOCK = threading.Lock()
_LOCK = threading.Lock()   # fayl variantida o'qib-o'zgartirib-yozish ketma-ket bajariladi


def _keyring_usable():
    try:
        import keyring
        from keyring.backends.fail import Keyring as FailKeyring
        backend = keyring.get_keyring()
        if isinstance(backend, FailKeyring):
            return None
        keyring.get_password(SERVICE, "__probe__")   # ombor qulflangan yoki ishlamasa istisno
        return keyring
    except Exception:
        return None


class SecretStore:
    def __init__(self, data_dir: Path, use_keyring: bool = True):
        self._dir = Path(data_dir)
        self._keyring = _keyring_usable() if use_keyring else None
        self.backend = "keyring" if self._keyring else "file"

    # ---- fayl varianti ----
    def _fernet(self) -> Fernet:
        key_path = self._dir / "secret.key"
        if not key_path.exists():
            with _KEY_LOCK:
                if not key_path.exists():
                    self._write_private(key_path, Fernet.generate_key())
        return Fernet(key_path.read_bytes())

    @staticmethod
    def _write_private(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)   # atomik: o'quvchi hech qachon yarim yozilgan faylni ko'rmaydi

    def _load(self) -> dict[str, str]:
        path = self._dir / "secrets.enc"
        if not path.exists():
            return {}
        try:
            return json.loads(self._fernet().decrypt(path.read_bytes()))
        except (InvalidToken, ValueError):
            return {}   # buzilgan fayl: kalitlar yo'q deb hisoblanadi, ilova ishlashda davom etadi

    def _save(self, data: dict[str, str]) -> None:
        self._write_private(self._dir / "secrets.enc", self._fernet().encrypt(json.dumps(data).encode()))

    # ---- umumiy interfeys ----
    def set(self, name: str, value: str) -> None:
        if self._keyring:
            self._keyring.set_password(SERVICE, name, value)
            return
        with _LOCK:
            data = self._load()
            data[name] = value
            self._save(data)

    def get(self, name: str) -> str | None:
        if self._keyring:
            return self._keyring.get_password(SERVICE, name)
        return self._load().get(name)

    def delete(self, name: str) -> None:
        if self._keyring:
            try:
                self._keyring.delete_password(SERVICE, name)
            except Exception:
                pass
            return
        with _LOCK:
            data = self._load()
            if data.pop(name, None) is not None:
                self._save(data)
