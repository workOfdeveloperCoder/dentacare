#!/usr/bin/env python3
"""Generate ../chatbot-config.js from .env for the demo website embed."""

from app.site_config import public_config, write_site_config


def main() -> None:
    path = write_site_config()
    print(f"Wrote {path}")
    for key, value in public_config().items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
