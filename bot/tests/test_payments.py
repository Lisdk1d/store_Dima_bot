"""Payment webhook security primitives (P1-10)."""

import hashlib
import hmac

from src.utils.payments import amounts_match, normalize_amount, verify_webhook_signature

SECRET = "payment-secret"


def _sign(body: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_valid_signature_accepted() -> None:
    body = b'{"event_id":"e1","amount":1000}'
    assert verify_webhook_signature(body, _sign(body), SECRET) is True


def test_tampered_body_rejected() -> None:
    body = b'{"event_id":"e1","amount":1000}'
    sig = _sign(body)
    assert verify_webhook_signature(b'{"event_id":"e1","amount":9999}', sig, SECRET) is False


def test_wrong_secret_rejected() -> None:
    body = b'{"x":1}'
    assert verify_webhook_signature(body, _sign(body, "other"), SECRET) is False


def test_missing_signature_or_secret_rejected() -> None:
    body = b'{"x":1}'
    assert verify_webhook_signature(body, None, SECRET) is False
    assert verify_webhook_signature(body, _sign(body), "") is False


def test_normalize_amount() -> None:
    assert normalize_amount("10 000 ₽") == "10000"
    assert normalize_amount(10000) == "10000"
    assert normalize_amount(None) == ""


def test_amounts_match() -> None:
    assert amounts_match("10000", "10 000 ₽") is True
    assert amounts_match(10000, "10 000 ₽") is True
    assert amounts_match("9999", "10 000 ₽") is False
    assert amounts_match("", "10 000 ₽") is False
