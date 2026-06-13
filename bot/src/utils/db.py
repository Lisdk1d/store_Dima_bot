"""PostgreSQL database access layer (replaces MongoDB/Motor)."""

import logging
import re
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert

from src.models import (
    CartItem,
    Order,
    OrderItem,
    Payment,
    Product,
    User,
    async_session,
    init_db,
)
from src.models.base import engine

logger = logging.getLogger(__name__)


class Database:
    """Async PostgreSQL wrapper preserving the bot's public API."""

    @staticmethod
    def _normalize_category_for_match(category: str) -> str:
        text = (category or "").strip().casefold()
        text = re.sub(r"[\u200b-\u200d\ufe0e\ufe0f]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text

    @staticmethod
    def _canonicalize_category_for_storage(category: str) -> str:
        text = (category or "").strip()
        text = re.sub(r"[\u200b-\u200d\ufe0e\ufe0f]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text

    def _deduplicate_categories(self, categories: list[str]) -> list[str]:
        unique_by_normalized: dict[str, str] = {}
        for raw_category in categories:
            if not raw_category:
                continue
            category = self._canonicalize_category_for_storage(raw_category)
            if not category:
                continue
            normalized = self._normalize_category_for_match(category)
            if not normalized:
                continue
            previous = unique_by_normalized.get(normalized)
            if previous is None or (len(category), category.casefold()) < (len(previous), previous.casefold()):
                unique_by_normalized[normalized] = category
        return sorted(unique_by_normalized.values(), key=str.casefold)

    async def _get_all_raw_categories(self, *, in_stock_only: bool) -> list[str]:
        async with async_session() as session:
            query = select(Product.category).distinct()
            if in_stock_only:
                query = query.where(Product.stock > 0)
            result = await session.scalars(query)
            return list(result.all())

    async def _get_category_aliases(self, category: str, *, in_stock_only: bool) -> list[str]:
        normalized_target = self._normalize_category_for_match(category)
        if not normalized_target:
            return []
        source_categories = await self._get_all_raw_categories(in_stock_only=in_stock_only)
        aliases = [
            existing
            for existing in source_categories
            if self._normalize_category_for_match(existing) == normalized_target
        ]
        return aliases or [category]

    async def resolve_existing_category_name(self, category: str) -> str:
        return self._canonicalize_category_for_storage(category)

    async def _merge_category_aliases(self, canonical_category: str) -> None:
        aliases = await self._get_category_aliases(canonical_category, in_stock_only=False)
        aliases_to_merge = [alias for alias in aliases if alias != canonical_category]
        if not aliases_to_merge:
            return
        async with async_session() as session:
            await session.execute(
                update(Product)
                .where(Product.category.in_(aliases_to_merge))
                .values(category=canonical_category)
            )
            await session.commit()

    async def get_unique_categories(self) -> list[str]:
        try:
            categories = await self._get_all_raw_categories(in_stock_only=True)
            return self._deduplicate_categories(categories)
        except Exception as error:
            logger.exception("Failed to fetch unique categories: %s", error)
            return []

    async def get_all_categories(self) -> list[str]:
        try:
            categories = await self._get_all_raw_categories(in_stock_only=False)
            return self._deduplicate_categories(categories)
        except Exception as error:
            logger.exception("Failed to fetch all categories: %s", error)
            return []

    async def get_models_by_category(self, category: str) -> list[str]:
        try:
            category_aliases = await self._get_category_aliases(category, in_stock_only=True)
            async with async_session() as session:
                result = await session.scalars(
                    select(Product.model)
                    .where(Product.category.in_(category_aliases), Product.stock > 0)
                    .distinct()
                )
                return list(result.all())
        except Exception as error:
            logger.exception("Failed to fetch models by category '%s': %s", category, error)
            return []

    async def get_product_details(self, model: str) -> dict | None:
        try:
            async with async_session() as session:
                product = await session.scalar(
                    select(Product).where(Product.model == model, Product.stock > 0)
                )
                return product.to_dict() if product else None
        except Exception as error:
            logger.exception("Failed to fetch product details for '%s': %s", model, error)
            return None

    async def get_product_by_model(self, model: str) -> dict | None:
        """Return product regardless of stock (for admin edit/delete)."""
        try:
            async with async_session() as session:
                product = await session.scalar(select(Product).where(Product.model == model))
                return product.to_dict() if product else None
        except Exception as error:
            logger.exception("Failed to fetch product '%s': %s", model, error)
            return None

    async def get_product_by_id(self, product_id: int) -> dict | None:
        try:
            async with async_session() as session:
                product = await session.get(Product, product_id)
                return product.to_dict() if product else None
        except Exception as error:
            logger.exception("Failed to fetch product id '%s': %s", product_id, error)
            return None

    async def get_all_products(self) -> list[dict]:
        async with async_session() as session:
            result = await session.scalars(select(Product).order_by(Product.category, Product.model))
            return [product.to_dict() for product in result.all()]

    async def check_connection(self) -> None:
        try:
            await init_db()
            async with engine.connect() as conn:
                await conn.execute(select(1))
            logger.info("✅ Успешное подключение к PostgreSQL")
        except Exception as error:
            logger.exception("❌ Ошибка подключения к PostgreSQL: %s", error)

    async def add_product(
        self,
        category: str,
        model: str,
        price: str,
        description: str,
        photo_id: str,
        stock: int = 1,
    ) -> int | None:
        logger.info(
            "add_product called: category=%r model=%r price=%r stock=%s",
            category,
            model,
            price,
            stock,
        )
        try:
            resolved_category = await self.resolve_existing_category_name(category)
            await self._merge_category_aliases(resolved_category)
            async with async_session() as session:
                product = Product(
                    category=resolved_category,
                    model=model,
                    description=description,
                    price=price,
                    photo_id=photo_id,
                    stock=stock,
                )
                session.add(product)
                await session.commit()
                await session.refresh(product)
                logger.info("add_product success: id=%s model=%r", product.id, product.model)
                return product.id
        except Exception as error:
            logger.exception("Ошибка при добавлении товара '%s': %s", model, error)
            return None

    async def update_product(self, model: str, **fields) -> bool:
        """Update product fields by model name."""
        allowed = {"category", "model", "description", "price", "photo_id", "stock"}
        updates = {key: value for key, value in fields.items() if key in allowed and value is not None}
        if not updates:
            return False
        try:
            async with async_session() as session:
                result = await session.execute(
                    update(Product).where(Product.model == model).values(**updates)
                )
                await session.commit()
                return result.rowcount > 0
        except Exception as error:
            logger.exception("Ошибка при обновлении товара '%s': %s", model, error)
            return False

    async def delete_model(self, category: str, model: str) -> bool:
        try:
            async with async_session() as session:
                result = await session.execute(
                    delete(Product).where(Product.category == category, Product.model == model)
                )
                await session.commit()
                return result.rowcount > 0
        except Exception as error:
            logger.exception("Ошибка при удалении товара '%s' из '%s': %s", model, category, error)
            return False

    async def delete_model_by_name(self, model: str) -> bool:
        try:
            async with async_session() as session:
                result = await session.execute(delete(Product).where(Product.model == model))
                await session.commit()
                return result.rowcount > 0
        except Exception as error:
            logger.exception("Ошибка при удалении модели '%s': %s", model, error)
            return False

    async def delete_category(self, category: str) -> int:
        """Delete all products in a category. Returns deleted count."""
        try:
            aliases = await self._get_category_aliases(category, in_stock_only=False)
            async with async_session() as session:
                result = await session.execute(
                    delete(Product).where(Product.category.in_(aliases))
                )
                await session.commit()
                return result.rowcount or 0
        except Exception as error:
            logger.exception("Ошибка при удалении категории '%s': %s", category, error)
            return 0

    async def create_user(self, user_id: int, username: str | None = None) -> None:
        normalized_username = f"@{username}" if username else None
        try:
            async with async_session() as session:
                stmt = insert(User).values(
                    id=user_id,
                    username=normalized_username,
                ).on_conflict_do_update(
                    index_elements=[User.id],
                    set_={"username": normalized_username},
                )
                await session.execute(stmt)
                await session.commit()
        except Exception as error:
            logger.exception("Ошибка при создании/обновлении пользователя '%s': %s", user_id, error)

    async def get_user_cart(self, user_id: int) -> list[dict]:
        return await self.get_cart(user_id)

    async def get_cart(self, user_id: int) -> list[dict]:
        try:
            async with async_session() as session:
                result = await session.scalars(
                    select(CartItem).where(CartItem.user_id == user_id).order_by(CartItem.id)
                )
                return [
                    {
                        "model_name": item.model_name,
                        "price": item.price,
                        "category_name": item.category_name,
                    }
                    for item in result.all()
                ]
        except Exception as error:
            logger.exception("Ошибка при получении корзины пользователя '%s': %s", user_id, error)
            return []

    async def add_to_cart(
        self,
        user_id: int,
        model_name: str,
        price: str,
        category_name: str | None = None,
    ) -> None:
        try:
            async with async_session() as session:
                await session.execute(
                    insert(User).values(id=user_id).on_conflict_do_nothing(index_elements=[User.id])
                )
                session.add(
                    CartItem(
                        user_id=user_id,
                        model_name=model_name,
                        price=price,
                        category_name=category_name,
                    )
                )
                await session.commit()
        except Exception as error:
            logger.exception(
                "Ошибка при добавлении в корзину пользователя '%s' модели '%s': %s",
                user_id,
                model_name,
                error,
            )

    async def clear_cart(self, user_id: int) -> bool:
        try:
            async with async_session() as session:
                await session.execute(delete(CartItem).where(CartItem.user_id == user_id))
                await session.commit()
                return True
        except Exception as error:
            logger.exception("Ошибка при очистке корзины пользователя '%s': %s", user_id, error)
            return False

    async def remove_item_from_cart(self, user_id: int, index: int) -> bool:
        if index < 0:
            return False
        cart_items = await self.get_cart(user_id)
        if index >= len(cart_items):
            return False
        try:
            async with async_session() as session:
                items = await session.scalars(
                    select(CartItem).where(CartItem.user_id == user_id).order_by(CartItem.id)
                )
                items_list = list(items.all())
                if index >= len(items_list):
                    return False
                await session.delete(items_list[index])
                await session.commit()
                return True
        except Exception as error:
            logger.exception(
                "Ошибка при удалении позиции корзины пользователя '%s' по индексу '%s': %s",
                user_id,
                index,
                error,
            )
            return False

    async def create_order(
        self,
        user_id: int,
        cart_items: list[dict],
        payment_method: str,
        total_amount: str | None = None,
        delivery_address: str | None = None,
        delivery_fee: str | None = None,
        status: str = "confirmed",
        payment_status: str = "completed",
    ) -> int | None:
        """Create order with items, delivery info, and payment record."""
        try:
            async with async_session() as session:
                order = Order(
                    user_id=user_id,
                    status=status,
                    payment_method=payment_method,
                    total_amount=total_amount,
                    delivery_address=delivery_address,
                    delivery_fee=delivery_fee,
                )
                session.add(order)
                await session.flush()

                for item in cart_items:
                    session.add(
                        OrderItem(
                            order_id=order.id,
                            model_name=item.get("model_name") or item.get("model", ""),
                            price=str(item.get("price", "")),
                            category_name=item.get("category_name"),
                            quantity=int(item.get("quantity", 1)),
                        )
                    )

                session.add(
                    Payment(
                        order_id=order.id,
                        method=payment_method,
                        status=payment_status,
                        amount=total_amount,
                        details="stub_payment",
                    )
                )
                await session.commit()
                await session.refresh(order)
                logger.info(
                    "Order created: id=%s user=%s status=%s method=%s",
                    order.id,
                    user_id,
                    status,
                    payment_method,
                )
                return order.id
        except Exception as error:
            logger.exception("Ошибка при создании заказа для пользователя '%s': %s", user_id, error)
            return None

    async def get_orders_count(self) -> int:
        async with async_session() as session:
            return await session.scalar(select(func.count()).select_from(Order)) or 0

    async def get_all_orders(self, limit: int = 100) -> list[dict]:
        """Return orders with user info for admin panel."""
        async with async_session() as session:
            from sqlalchemy.orm import selectinload
            result = await session.scalars(
                select(Order)
                .options(selectinload(Order.items), selectinload(Order.user))
                .order_by(Order.created_at.desc())
                .limit(limit)
            )
            orders = []
            for order in result.all():
                user = order.user
                orders.append({
                    "id": order.id,
                    "user_id": order.user_id,
                    "username": user.username if user else None,
                    "status": order.status,
                    "payment_method": order.payment_method,
                    "total_amount": order.total_amount,
                    "delivery_address": order.delivery_address,
                    "delivery_fee": order.delivery_fee,
                    "created_at": order.created_at.isoformat() if order.created_at else None,
                    "items": [
                        {
                            "model_name": item.model_name,
                            "price": item.price,
                            "category_name": item.category_name,
                            "quantity": item.quantity,
                        }
                        for item in order.items
                    ],
                })
            return orders

    async def get_recent_orders(self, limit: int = 20) -> list[dict]:
        return await self.get_all_orders(limit=limit)

    async def get_products_count(self) -> int:
        async with async_session() as session:
            return await session.scalar(select(func.count()).select_from(Product)) or 0


db = Database()
