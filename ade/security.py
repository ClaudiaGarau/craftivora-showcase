from __future__ import annotations

from typing import Any


SENSITIVE_FRAGMENTS = ("password", "passwd", "secret", "token", "api_key", "apikey", "private_key", "cookie")


def sanitize_context(value: Any, *, max_string: int = 50000, depth: int = 0) -> Any:
    if depth > 8:
        return "[TRUNCATED_DEPTH]"
    if isinstance(value, dict):
        clean = {}
        for key, item in list(value.items())[:500]:
            label = str(key)
            if any(fragment in label.lower() for fragment in SENSITIVE_FRAGMENTS):
                clean[label] = "[REDACTED]"
            else:
                clean[label] = sanitize_context(item, max_string=max_string, depth=depth + 1)
        return clean
    if isinstance(value, list):
        return [sanitize_context(item, max_string=max_string, depth=depth + 1) for item in value[:500]]
    if isinstance(value, str):
        return value[:max_string]
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return str(value)[:max_string]
