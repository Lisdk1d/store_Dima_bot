"""Signed, time-limited links to the customer-facing payment page.

A regular customer is not a Telegram admin, so the initData scheme in
``src.utils.auth`` does not apply here. Instead the bot signs a small payload
(order id, user id, expiry) with ``PAYMENT_LINK_SECRET`` when it sends the
"Pay" button; the payment-page service verifies it on every request. A leaked
link only grants access to that one order's payment page until it expires —
never admin access, never the ability to forge a provider webhook.
"""

import base64
import hashlib
import hmac
import time

_SEPARATOR = "."


class PaymentLinkError(Exception):
    """Raised when a payment-link token is malformed, tampered, or expired."""


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def sign_payment_token(order_id: int, user_id: int, *, secret: str, ttl_seconds: int) -> str:
    """Build `<base64url(payload)>.<hex hmac>` for the given order/user pair."""
    expires_at = int(time.time()) + ttl_seconds
    payload = f"{order_id}:{user_id}:{expires_at}"
    encoded_payload = _b64url_encode(payload.encode())
    signature = hmac.new(secret.encode(), encoded_payload.encode(), hashlib.sha256).hexdigest()
    return f"{encoded_payload}{_SEPARATOR}{signature}"


def verify_payment_token(token: str, *, secret: str) -> dict[str, int]:
    """Verify a token and return ``{"order_id": int, "user_id": int}``.

    Raises ``PaymentLinkError`` on any malformed, tampered, or expired token —
    callers only ever need to catch this one exception type.
    """
    if not token or _SEPARATOR not in token:
        raise PaymentLinkError("malformed token")

    encoded_payload, _, signature = token.partition(_SEPARATOR)
    expected_signature = hmac.new(secret.encode(), encoded_payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_signature, signature):
        raise PaymentLinkError("signature mismatch")

    try:
        payload = _b64url_decode(encoded_payload).decode()
        order_id_str, user_id_str, expires_at_str = payload.split(":")
        order_id, user_id, expires_at = int(order_id_str), int(user_id_str), int(expires_at_str)
    except (ValueError, UnicodeDecodeError) as error:
        raise PaymentLinkError("malformed payload") from error

    if time.time() > expires_at:
        raise PaymentLinkError("token expired")

    return {"order_id": order_id, "user_id": user_id}
