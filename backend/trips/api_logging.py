from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

from django.conf import settings


SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "x-goog-api-key",
    "x-rapidapi-key",
    "password",
    "secret",
    "token",
    "username",
}


def _root_logs_dir() -> Path:
    base_dir = getattr(settings, "BASE_DIR", None)
    if base_dir:
        return Path(base_dir).parent / "logs" / "api_responses"
    return Path("logs") / "api_responses"


def _sanitize_key(key: str) -> str:
    return key.strip().lower().replace("-", "_")


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return _sanitize_map(value)
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    return value


def _sanitize_map(payload: Dict[str, Any] | None) -> Dict[str, Any]:
    if not payload:
        return {}
    result: Dict[str, Any] = {}
    for raw_key, raw_value in payload.items():
        key = str(raw_key)
        normalized_key = _sanitize_key(key)
        if normalized_key in SENSITIVE_KEYS or any(token in normalized_key for token in ("api_key", "secret", "token", "password")):
            result[key] = "***REDACTED***"
            continue
        result[key] = _sanitize_value(raw_value)
    return result


def _sanitize_url(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if not query:
        return url

    sanitized_query = {}
    for key, values in query.items():
        normalized_key = _sanitize_key(key)
        if normalized_key in SENSITIVE_KEYS or "api_key" in normalized_key or "token" in normalized_key:
            sanitized_query[key] = ["***REDACTED***"]
        else:
            sanitized_query[key] = values

    query_parts = []
    for key, values in sanitized_query.items():
        for value in values:
            query_parts.append(f"{key}={value}")
    sanitized_qs = "&".join(query_parts)
    return parsed._replace(query=sanitized_qs).geturl()


def _provider_slug(provider: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", provider.strip().lower())
    return slug or "unknown_provider"


def log_api_response(
    *,
    provider: str,
    method: str,
    url: str,
    request_headers: Dict[str, Any] | None = None,
    request_params: Dict[str, Any] | None = None,
    request_payload: Dict[str, Any] | None = None,
    status_code: int | None = None,
    response_body: Any | None = None,
    error: str | None = None,
    duration_ms: int | None = None,
) -> None:
    try:
        target_dir = _root_logs_dir()
        target_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now(timezone.utc)
        filename = f"{now.strftime('%Y-%m-%d')}_{_provider_slug(provider)}.jsonl"
        log_file = target_dir / filename

        entry = {
            "timestamp_utc": now.isoformat(),
            "provider": provider,
            "method": method,
            "url": _sanitize_url(url),
            "request": {
                "headers": _sanitize_map(request_headers),
                "params": _sanitize_map(request_params),
                "payload": _sanitize_map(request_payload),
            },
            "status_code": status_code,
            "duration_ms": duration_ms,
            "success": error is None,
            "error": error,
            "response": _sanitize_value(response_body),
        }

        with log_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        # Logging must never interrupt API request flow.
        return
