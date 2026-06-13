"""Product ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(255), index=True)
    model: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text)
    price: Mapped[str] = mapped_column(String(128))
    photo_id: Mapped[str] = mapped_column(String(512))
    stock: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "model": self.model,
            "description": self.description,
            "price": self.price,
            "photo_id": self.photo_id,
            "stock": self.stock,
            "created_at": self.created_at,
        }
