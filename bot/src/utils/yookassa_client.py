"""Thin async client for the YooKassa REST API (v3).

Only the two calls this bot needs:
  * create_payment — returns a payment whose confirmation_url the customer opens
  * get_payment    — the authoritative payment object, used to verify the
                     (unsigned) webhook notifications

Auth is HTTP Basic with shopId:secretKey. Amounts are whole-ruble strings here
(orders cannot represent kopecks), formatted to YooKassa's required "NNNN.00".
"""

from __future__ import annotations

import logging
import re
import uuid

import httpx

logger = logging.getLogger(__name__)

_API_BASE = "https://api.yookassa.ru/v3"
_NON_DIGITS = re.compile(r"\D")
_REQUEST_TIMEOUT = 20.0


class YooKassaError(Exception):
    """Raised when the YooKassa API errors out or is unreachable."""


def rubles_to_minor_units(order_total: str | int | None) -> str:
    """Convert a stored order total ('10 000 ₽') to YooKassa's '10000.00' string."""
    digits = _NON_DIGITS.sub("", str(order_total if order_total is not None else ""))
    if not digits:
        raise YooKassaError(f"cannot derive amount from order total {order_total!r}")
    return f"{int(digits)}.00"


def yookassa_amount_matches_order(yookassa_value: str | None, order_total: str | None) -> bool:
    """True when a YooKassa amount value ('10000.00') equals the order total.

    Returns False for any amount with non-zero kopecks, since order totals here
    cannot represent fractional rubles.
    """
    try:
        expected = rubles_to_minor_units(order_total)
    except YooKassaError:
        return False
    return str(yookassa_value or "").strip() == expected


async def create_payment(
    *,
    client: httpx.AsyncClient,
    shop_id: str,
    secret_key: str,
    amount_value: str,
    order_id: int,
    description: str,
    return_url: str,
    idempotence_key: str | None = None,
) -> dict:
    """Create a YooKassa payment and return the parsed payment object.

    ``amount_value`` must already be in '10000.00' form (see rubles_to_minor_units).
    Raises ``YooKassaError`` on transport failure or a non-2xx response.
    """
    body = {
        "amount": {"value": amount_value, "currency": "RUB"},
        "capture": True,
        "confirmation": {"type": "redirect", "return_url": return_url},
        "description": description,
        "metadata": {"order_id": str(order_id)},
    }
    headers = {"Idempotence-Key": idempotence_key or uuid.uuid4().hex}
    try:
        response = await client.post(
            f"{_API_BASE}/payments",
            json=body,
            headers=headers,
            auth=(shop_id, secret_key),
            timeout=_REQUEST_TIMEOUT,
        )
    except httpx.HTTPError as error:
        raise YooKassaError(f"create_payment request failed: {error}") from error
    if response.status_code >= 300:
        raise YooKassaError(f"create_payment HTTP {response.status_code}")
    return response.json()


async def get_payment(
    *,
    client: httpx.AsyncClient,
    shop_id: str,
    secret_key: str,
    payment_id: str,
) -> dict:
    """Fetch the authoritative payment object by id."""
    try:
        response = await client.get(
            f"{_API_BASE}/payments/{payment_id}",
            auth=(shop_id, secret_key),
            timeout=_REQUEST_TIMEOUT,
        )
    except httpx.HTTPError as error:
        raise YooKassaError(f"get_payment request failed: {error}") from error
    if response.status_code >= 300:
        raise YooKassaError(f"get_payment HTTP {response.status_code}")
    return response.json()
