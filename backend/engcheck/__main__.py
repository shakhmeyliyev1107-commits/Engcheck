"""Ishga tushirish: python -m engcheck"""
import uvicorn

from .api.app import create_app
from .config import get_settings


def main() -> None:
    settings = get_settings()
    print(f"EngCheck: http://{settings.host}:{settings.port}  (ma'lumotlar: {settings.data_dir})")
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port, log_level="warning")


if __name__ == "__main__":
    main()
