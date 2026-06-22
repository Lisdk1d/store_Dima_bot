"""Log redaction of bot-token-shaped secrets (P2-17)."""

import logging

from src.utils.logging_config import RedactingFilter


def _record(msg: str, *args: object) -> logging.LogRecord:
    return logging.LogRecord("t", logging.INFO, __file__, 1, msg, args, None)


def test_bot_token_is_redacted() -> None:
    rec = _record("set webhook with token 123456789:AAFakeTokenValue_abcdefghijklmnop")
    RedactingFilter().filter(rec)
    assert "123456789:AAFakeTokenValue" not in rec.getMessage()
    assert "REDACTED" in rec.getMessage()


def test_token_redacted_through_format_args() -> None:
    rec = _record("token=%s", "987654321:ZZanotherFakeToken_abcdefghijklmnop")
    RedactingFilter().filter(rec)
    assert "987654321:ZZ" not in rec.getMessage()


def test_plain_message_unchanged() -> None:
    rec = _record("ordinary log line with no secrets")
    RedactingFilter().filter(rec)
    assert rec.getMessage() == "ordinary log line with no secrets"
