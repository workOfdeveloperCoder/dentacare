"""Write website chatbot-config.js from .env values."""

from __future__ import annotations

import json
from pathlib import Path

from app.config import (
    API_URL,
    DEFAULT_FLOW,
    SITE_CONFIG_PATH,
    SITE_URL,
)


def public_config() -> dict:
    return {
        "apiUrl": API_URL,
        "siteUrl": SITE_URL,
        "flowKey": DEFAULT_FLOW,
        "widgetSrc": f"{API_URL}/widget.js",
    }


def write_site_config(path: Path | None = None) -> Path:
    target = path or SITE_CONFIG_PATH
    config = public_config()
    payload = json.dumps(config, indent=2)

    contents = (
        "// Generated from dental-chatbot-v2/.env — do not edit by hand.\n"
        "// Re-run the API or: python scripts/write_site_config.py\n"
        f"window.CHATBOT_CONFIG = {payload};\n"
    )

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(contents, encoding="utf-8")
    return target


if __name__ == "__main__":
    written = write_site_config()
    print(f"Wrote {written}")
    print(json.dumps(public_config(), indent=2))
