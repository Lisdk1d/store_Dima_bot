"""YooKassa webhook reconciliation logic (Step 7).

Exercises reconcile_payment() against an authoritative payment object with the
DB layer and notifications faked — no Postgres, no network, no real bot.
"""

import asyncio

import pytest

import payment_api

ORDER = {"id": 7, "user_id": 555, "total_amount": "10 000 ₽", "delivery_address": "ул. Тест, 1"}


@pytest.fixture(autouse=True)
def _fakes(monkeypatch: pytest.MonkeyPatch):
    calls: dict = {"update": [], "notify": []}

    async def fake_get_order_by_id(order_id: int):
        return dict(ORDER) if order_id == ORDER["id"] else None

    async def fake_get_by_provider(provider: str, provider_payment_id: str):
        return None

    async def fake_update(order_id: int, *, status: str, order_status=None, details=None):
        calls["update"].append((order_id, status, order_status))
        return True

    async def fake_notify(order: dict):
        calls["notify"].append(order["id"])

    monkeypatch.setattr(payment_api.db, "get_order_by_id", fake_get_order_by_id)
    monkeypatch.setattr(payment_api.db, "get_order_by_provider_payment_id", fake_get_by_provider)
    monkeypatch.setattr(payment_api.db, "update_payment_status", fake_update)
    monkeypatch.setattr(payment_api, "_notify_paid", fake_notify)
    return calls


def _payment(status: str, amount: str = "10000.00", order_id: int = 7) -> dict:
    return {
        "id": "pay-abc",
        "status": status,
        "amount": {"value": amount, "currency": "RUB"},
        "metadata": {"order_id": str(order_id)},
    }


def test_succeeded_marks_paid_and_notifies(_fakes) -> None:
    result = asyncio.run(payment_api.reconcile_payment(_payment("succeeded")))
    assert result == "paid"
    assert _fakes["update"] == [(7, "succeeded", "confirmed")]
    assert _fakes["notify"] == [7]


def test_amount_mismatch_does_not_mark_paid(_fakes) -> None:
    result = asyncio.run(payment_api.reconcile_payment(_payment("succeeded", amount="9999.00")))
    assert result == "amount_mismatch"
    assert _fakes["update"] == []
    assert _fakes["notify"] == []


def test_canceled_marks_cancelled(_fakes) -> None:
    result = asyncio.run(payment_api.reconcile_payment(_payment("canceled")))
    assert result == "canceled"
    assert _fakes["update"] == [(7, "canceled", "cancelled")]


def test_pending_is_noop(_fakes) -> None:
    result = asyncio.run(payment_api.reconcile_payment(_payment("waiting_for_capture")))
    assert result == "pending"
    assert _fakes["update"] == []


def test_unknown_order_is_ignored(_fakes) -> None:
    result = asyncio.run(payment_api.reconcile_payment(_payment("succeeded", order_id=999)))
    assert result == "ignored"
    assert _fakes["update"] == []
