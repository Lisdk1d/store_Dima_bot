"""YooKassa client: amount conversion + request shape (Step 3)."""

import asyncio
import base64
import json

import httpx
import pytest

from src.utils.yookassa_client import (
    YooKassaError,
    create_payment,
    get_payment,
    rubles_to_minor_units,
    yookassa_amount_matches_order,
)

SHOP_ID = "shop-123"
SECRET_KEY = "test-secret-key"


def test_rubles_to_minor_units() -> None:
    assert rubles_to_minor_units("10 000 ₽") == "10000.00"
    assert rubles_to_minor_units("0 ₽") == "0.00"
    assert rubles_to_minor_units(5000) == "5000.00"


def test_rubles_to_minor_units_rejects_empty() -> None:
    with pytest.raises(YooKassaError):
        rubles_to_minor_units("")
    with pytest.raises(YooKassaError):
        rubles_to_minor_units(None)


def test_yookassa_amount_matches_order() -> None:
    assert yookassa_amount_matches_order("10000.00", "10 000 ₽") is True
    assert yookassa_amount_matches_order("9999.00", "10 000 ₽") is False
    assert yookassa_amount_matches_order("10000.50", "10 000 ₽") is False  # nonzero kopecks
    assert yookassa_amount_matches_order("", "10 000 ₽") is False


def _basic_auth(request: httpx.Request) -> tuple[str, str]:
    raw = request.headers["authorization"].split(" ", 1)[1]
    user, _, password = base64.b64decode(raw).decode().partition(":")
    return user, password


def test_create_payment_sends_expected_request() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["idem"] = request.headers.get("idempotence-key")
        captured["auth"] = _basic_auth(request)
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "pay-1",
                "status": "pending",
                "confirmation": {"type": "redirect", "confirmation_url": "https://yoo/pay"},
                "amount": {"value": "10000.00", "currency": "RUB"},
            },
        )

    async def run() -> dict:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await create_payment(
                client=client,
                shop_id=SHOP_ID,
                secret_key=SECRET_KEY,
                amount_value="10000.00",
                order_id=42,
                description="Order #42",
                return_url="https://shop.example/pay/42",
                idempotence_key="fixed-key",
            )

    payment = asyncio.run(run())
    assert payment["id"] == "pay-1"
    assert captured["url"].endswith("/v3/payments")
    assert captured["idem"] == "fixed-key"
    assert captured["auth"] == (SHOP_ID, SECRET_KEY)
    assert captured["body"]["amount"] == {"value": "10000.00", "currency": "RUB"}
    assert captured["body"]["metadata"] == {"order_id": "42"}
    assert captured["body"]["confirmation"]["return_url"] == "https://shop.example/pay/42"


def test_create_payment_raises_on_error_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"type": "error", "code": "invalid_request"})

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await create_payment(
                client=client,
                shop_id=SHOP_ID,
                secret_key=SECRET_KEY,
                amount_value="10000.00",
                order_id=1,
                description="x",
                return_url="https://shop.example/pay/1",
            )

    with pytest.raises(YooKassaError):
        asyncio.run(run())


def test_get_payment_returns_authoritative_object() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v3/payments/pay-9"
        return httpx.Response(200, json={"id": "pay-9", "status": "succeeded"})

    async def run() -> dict:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await get_payment(
                client=client, shop_id=SHOP_ID, secret_key=SECRET_KEY, payment_id="pay-9"
            )

    payment = asyncio.run(run())
    assert payment["status"] == "succeeded"
