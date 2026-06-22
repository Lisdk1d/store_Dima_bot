"""Input validation bounds on API request models (P2-12)."""

import pytest
from pydantic import ValidationError

from api_main import OrderItemUpdate, ProductCreate


def test_product_create_rejects_empty_model() -> None:
    with pytest.raises(ValidationError):
        ProductCreate(category="c", model="", description="d", price="1")


def test_product_create_rejects_negative_stock() -> None:
    with pytest.raises(ValidationError):
        ProductCreate(category="c", model="m", description="d", price="1", stock=-1)


def test_product_create_rejects_overlong_model() -> None:
    with pytest.raises(ValidationError):
        ProductCreate(category="c", model="x" * 513, description="d", price="1")


def test_product_create_defaults_ok() -> None:
    product = ProductCreate(category="c", model="m", description="d", price="100")
    assert product.stock == 1 and product.photo_id == ""


def test_order_item_rejects_zero_quantity() -> None:
    with pytest.raises(ValidationError):
        OrderItemUpdate(model_name="m", price="1", quantity=0)
