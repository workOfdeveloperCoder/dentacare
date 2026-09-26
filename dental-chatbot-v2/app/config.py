import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
SITE_ROOT = BASE_DIR.parent

load_dotenv(BASE_DIR / ".env")


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip()


def _strip_slash(url: str) -> str:
    return url.rstrip("/")


DB_CONFIG = {
    "dbname": _env("CHATBOT_DB_NAME", "dental_chatbot_v2"),
    "user": _env("CHATBOT_DB_USER", "postgres"),
    "password": _env("CHATBOT_DB_PASSWORD", "root"),
    "host": _env("CHATBOT_DB_HOST", "localhost"),
    "port": int(_env("CHATBOT_DB_PORT", "5432")),
}

API_HOST = _env("CHATBOT_API_HOST", "127.0.0.1")
API_PORT = int(_env("CHATBOT_API_PORT", "8000"))
API_URL = _strip_slash(
    _env(
        "CHATBOT_API_URL",
        f"http://{API_HOST}:{API_PORT}",
    )
)

SITE_URL = _strip_slash(
    _env("CHATBOT_SITE_URL", "http://127.0.0.1:4500")
)

DEFAULT_FLOW = _env("CHATBOT_DEFAULT_FLOW", "dental_reception")

CORS_ORIGINS = [
    origin.strip()
    for origin in _env(
        "CHATBOT_CORS_ORIGINS",
        f"{SITE_URL},http://localhost:5500,http://127.0.0.1:4500",
    ).split(",")
    if origin.strip()
]

FLOW_DIR = Path(_env("CHATBOT_FLOW_DIR", str(BASE_DIR / "flow")))
FRONTEND_DIR = BASE_DIR / "frontend"
DATABASE_DIR = BASE_DIR / "database"
SITE_CONFIG_PATH = Path(
    _env("CHATBOT_SITE_CONFIG_PATH", str(SITE_ROOT / "chatbot-config.js"))
)
