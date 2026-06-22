"""Audit log of sensitive admin actions."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    actor_id: Mapped[int] = mapped_column(BigInteger, index=True)
    actor_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(64), index=True)  # e.g. "product.delete"
    object_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    object_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)  # no PII — keys only
    request_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
