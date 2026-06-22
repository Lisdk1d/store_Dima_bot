"""Central logging setup with secret/PII redaction.

A single ``configure_logging()`` entrypoint installs one root handler whose
filter scrubs bot-token-shaped strings and the configured secrets from every
log line, so tokens/keys never reach the logs.
"""

import logging
import re

from src.utils.config import settings

# Telegram bot tokens look like "<digits>:<35+ url-safe chars>".
_TOKEN_RE = re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b")
_REDACTED = "***REDACTED***"
_MIN_SECRET_LEN = 6


class RedactingFilter(logging.Filter):
    """Removes bot tokens and configured secret values from log messages."""

    def __init__(self) -> None:
        super().__init__()
        candidates = {
            settings.BOT_TOKEN,
            settings.API_SECRET_KEY,
            settings.WEBHOOK_SECRET,
            settings.PAYMENT_WEBHOOK_SECRET,
            settings.DB_PASS,
        }
        # Sort longest-first so overlapping secrets redact fully.
        self._secrets = sorted(
            (s for s in candidates if s and len(s) >= _MIN_SECRET_LEN), key=len, reverse=True
        )

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True
        redacted = _TOKEN_RE.sub(_REDACTED, message)
        for secret in self._secrets:
            if secret in redacted:
                redacted = redacted.replace(secret, _REDACTED)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def configure_logging(level: int = logging.INFO) -> None:
    """Install a single redacting root handler (idempotent)."""
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s"))
    handler.addFilter(RedactingFilter())

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)
