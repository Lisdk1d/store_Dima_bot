"""Audit log model and request-id correlation (P1-9)."""

from src.models import AuditLog
from src.utils.request_context import get_request_id, new_request_id


def test_new_request_id_is_unique_and_readable() -> None:
    first = new_request_id()
    assert get_request_id() == first
    assert len(first) == 32
    second = new_request_id()
    assert second != first
    assert get_request_id() == second


def test_audit_log_model_fields() -> None:
    entry = AuditLog(
        actor_id=42,
        actor_username="boss",
        action="order.delete",
        object_type="order",
        object_id="7",
        detail="fields=status",
        request_id="abc",
    )
    assert entry.actor_id == 42
    assert entry.action == "order.delete"
    assert entry.object_id == "7"
