"""Structured (JSON-lines) logging with secret redaction.

Events go to the "musicmind" logger. Nothing is configured by default, so
importing the package never writes files, and a NullHandler keeps unconfigured use silent
(otherwise Python prints WARNING events to stderr). Call configure_logging() to enable a
JSON-lines file.

Privacy rules enforced here:
* API keys and tokens are redacted from every message and field (both known
  patterns such as sk-... and the literal value of ANTHROPIC_API_KEY).
* The raw user query is never logged: only its length and a short hash.
"""
import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

LOGGER_NAME = "musicmind"
REDACTED = "[REDACTED]"
_SECRET_ENV_VARS = ("ANTHROPIC_API_KEY",)

# Library best practice: with no handler, Python's "last resort" handler would print WARNING-level
# events (blocked input, low confidence) to stderr. A NullHandler keeps unconfigured use silent;
# configure_logging() adds a real handler alongside it. The check avoids duplicates on re-import.
if not any(isinstance(h, logging.NullHandler) for h in logging.getLogger(LOGGER_NAME).handlers):
    logging.getLogger(LOGGER_NAME).addHandler(logging.NullHandler())

_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{8,}"), REDACTED),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-]{8,}"), f"Bearer {REDACTED}"),
    # "api_key: value" / "x-api-key=value" (a name followed by : or =, not plain prose)
    (re.compile(r"(?i)\b(api[_-]?key|x-api-key|authorization)(\s*[:=]\s*)\S+"), rf"\1\2{REDACTED}"),
]


def redact(value: Any) -> str:
    """Return str(value) with API keys and tokens replaced by [REDACTED]."""
    text = str(value)
    for name in _SECRET_ENV_VARS:
        secret = os.environ.get(name)
        if secret and len(secret) >= 8:
            text = text.replace(secret, REDACTED)
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_clean(v) for v in value]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return redact(value)


def query_fingerprint(text: Any) -> Dict[str, Any]:
    """Length and short hash of a query, safe to log instead of the text itself."""
    raw = text if isinstance(text, str) else ("" if text is None else str(text))
    return {"query_chars": len(raw), "query_id": hashlib.sha256(raw.encode("utf-8")).hexdigest()[:10]}


def log_event(logger: logging.Logger, level: int, event: str, message: str, **fields: Any) -> None:
    """Emit one structured event (message and fields are redacted)."""
    logger.log(level, redact(message), extra={"event": event, "fields": fields})


class JsonFormatter(logging.Formatter):
    """One JSON object per line: ts, level, event, message and event fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "event": getattr(record, "event", "log"),
            "message": redact(record.getMessage()),
        }
        payload.update(_clean(getattr(record, "fields", {})))
        return json.dumps(payload, ensure_ascii=False, sort_keys=False)


def configure_logging(log_file: Optional[str] = None, level: str = "INFO", mode: str = "a") -> logging.Handler:
    """Attach a JSON-lines handler to the "musicmind" logger (idempotent).

    Returns the handler so callers can remove it. With log_file=None a stream
    handler (stderr) is used.
    """
    logger = logging.getLogger(LOGGER_NAME)
    for old in [h for h in logger.handlers if getattr(h, "_musicmind", False)]:
        logger.removeHandler(old)
        old.close()
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handler: logging.Handler = logging.FileHandler(log_file, mode=mode, encoding="utf-8")
    else:
        handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler._musicmind = True  # marker so we only ever remove our own handler
    logger.addHandler(handler)
    logger.setLevel(level)
    return handler
