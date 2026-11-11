"""Ishga tushirish:  python -m engcheck [--port N] [--data-dir D]
Bazani shifrlash:  python -m engcheck encrypt-db [--data-dir D]
"""
import argparse
import json
import os
import signal
import socket
import sys
import threading
from pathlib import Path

import uvicorn

from .api.app import create_app
from .config import get_settings
from .core import dbcrypt
from .core.secrets import SecretStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="engcheck")
    parser.add_argument("command", nargs="?", choices=["serve", "encrypt-db"], default="serve")
    parser.add_argument("--port", type=int, default=None, help="0 — bo'sh portni tanlash")
    parser.add_argument("--data-dir", default=None)
    args = parser.parse_args(argv)
    settings = get_settings(args.data_dir, args.port)

    if args.command == "encrypt-db":
        try:
            backup = dbcrypt.encrypt_database(settings, SecretStore(settings.data_dir))
        except dbcrypt.AlreadyEncrypted:
            print("Baza allaqachon shifrlangan.")
            return 0
        except dbcrypt.EncryptionUnavailable:
            print('sqlcipher3 o\'rnatilmagan:  pip install -e "backend[encryption]"', file=sys.stderr)
            return 1
        except FileNotFoundError:
            print("Baza topilmadi — shifrlanadigan narsa yo'q.", file=sys.stderr)
            return 1
        print(f"Baza shifrlandi. Ochiq nusxa: {backup}\nTekshirib ko'rgach, bu faylni o'zingiz o'chiring.")
        return 0

    # Soket avval ochiladi va uvicorn'ga beriladi: "ready" satri chiqqanda port haqiqatan tinglayotgan bo'ladi
    # va tanlangan portni boshqa jarayon egallab ololmaydi.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((settings.host, settings.port))
    except OSError as exc:
        print(json.dumps({"event": "error", "code": "port_in_use", "detail": str(exc)}), flush=True)
        return 3
    sock.listen(128)
    settings.port = sock.getsockname()[1]
    try:
        dist = os.environ.get("ENGCHECK_FRONTEND_DIST")   # yig'ilgan ilovada interfeys fayllari joyi
        app = create_app(settings, Path(dist)) if dist else create_app(settings)
    except dbcrypt.DatabaseLocked as exc:
        print(json.dumps({"event": "error", "code": "database_locked", "detail": str(exc)}), flush=True)
        return 2

    async def _ready():   # desktop qobiq shu satrni kutadi
        print(json.dumps({"event": "ready", "port": settings.port}), flush=True)

    app.router.on_startup.append(_ready)
    if os.environ.get("ENGCHECK_EXIT_WITH_PARENT") == "1":
        # Qobiq (ota jarayon) yopilsa yoki yiqilsa, stdin yopiladi — xizmat yetim bo'lib qolmay, o'zi to'xtaydi.
        def _watch_parent():
            try:
                sys.stdin.buffer.read()
            finally:
                os.kill(os.getpid(), signal.SIGTERM)
        threading.Thread(target=_watch_parent, daemon=True).start()

    print(f"EngCheck: http://{settings.host}:{settings.port}  (ma'lumotlar: {settings.data_dir})", file=sys.stderr)
    uvicorn.Server(uvicorn.Config(app, log_level="warning")).run(sockets=[sock])
    return 0


if __name__ == "__main__":
    sys.exit(main())
