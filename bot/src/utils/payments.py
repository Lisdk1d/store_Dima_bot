"""Provider-agnostic payment-webhook helpers.

These primitives are provider-independent and fully tested:
  * verify_webhook_signature — constant-time HMAC-SHA256 over the raw body
  * normalize_amount / amounts_match — server-side amount verification

The exact signature scheme, header name, and JSON payload shape differ per
provider (ЮKassa, CloudPayments, Stripe, …). Finalize the parsing in the
webhook endpoint once a provider is chosen; the security primitives here stay
the same.
"""

import hashlib
import hmac
import re

_NON_DIGITS = re.compile(r"\D")


def verify_webhook_signature(body: bytes, signature: str | None, secret: str) -> bool:
    """Constant-time HMAC-SHA256 verification of the raw request body."""
    if not signature or not secret:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip())


def normalize_amount(value: str | int | float | None) -> str:
    """Reduce a money value to its digits only ('10 000 ₽' -> '10000')."""
    return _NON_DIGITS.sub("", str(value if value is not None else ""))


def amounts_match(provider_amount: str | int | float | None, order_total: str | None) -> bool:
    """True when the provider-reported amount matches the order's stored total.

    Compares digit-normalized values; minor-unit (kopeck) scaling must be
    reconciled per provider before this returns true for such payloads.
    """
    provider = normalize_amount(provider_amount)
    order = normalize_amount(order_total)
    return bool(provider) and provider == order
