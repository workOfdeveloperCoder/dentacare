from __future__ import annotations

import re
from typing import Any


PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")


def render_template(
    template: str | None,
    values: dict[str, Any] | None = None,
) -> str:
    if not template:
        return ""

    values = values or {}

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        value = _lookup(values, key)
        if value is None:
            return ""
        return str(value)

    return PLACEHOLDER.sub(replace, template)


def format_named(
    template: str,
    **kwargs: Any,
) -> str:
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        return template


def _lookup(values: dict[str, Any], key: str) -> Any:
    current: Any = values

    for part in key.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None

    return current
