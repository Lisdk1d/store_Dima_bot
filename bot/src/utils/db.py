from src.utils.config import settings
from motor.motor_asyncio import AsyncIOMotorClient
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self.client = AsyncIOMotorClient(settings.MONGO_URL)
        self.db = self.client[settings.DB_NAME]

        self.users = self.db.users
        self.products = self.db.products
        self._in_stock_filter = {"stock": {"$gt": 0}}

    async def get_unique_categories(self):
        """Return categories that have at least one product in stock."""
        try:
            return await self.products.distinct("category", self._in_stock_filter)
        except Exception as error:
            logger.exception("Failed to fetch unique categories: %s", error)
            return []

    async def get_all_categories(self):
        """Return all categories present in DB."""
        try:
            categories = await self.products.distinct("category")
            return [category for category in categories if category]
        except Exception as error:
            logger.exception("Failed to fetch all categories: %s", error)
            return []

    async def get_models_by_category(self, category: str):
        """Return available models for a given category."""
        query = {"category": category, **self._in_stock_filter}
        try:
            return await self.products.distinct("model", query)
        except Exception as error:
            logger.exception("Failed to fetch models by category '%s': %s", category, error)
            return []

    async def get_product_details(self, model: str):
        """Return product document by model only if it is in stock."""
        query = {"model": model, **self._in_stock_filter}
        try:
            return await self.products.find_one(query)
        except Exception as error:
            logger.exception("Failed to fetch product details for '%s': %s", model, error)
            return None

    async def check_connection(self):
        try:
            await self.client.admin.command("ping")
            logger.info("✅ Успешное подключение к MongoDB")
        except Exception as error:
            logger.exception("❌ Ошибка подключения к MongoDB: %s", error)

    async def add_product(self, category: str, model: str, price: int, description: str, photo_id: str, stock: int = 1):
        try:
            document = {
                "category": category,
                "model": model,
                "description": description,
                "price": price,
                "photo_id": photo_id,
                "stock": stock,
                "created_at": datetime.now(),
            }
            result = await self.products.insert_one(document)
            return result.inserted_id
        except Exception as error:
            logger.exception("Ошибка при добавлении товара '%s': %s", model, error)
            return None

    async def delete_model(self, category: str, model: str):
        try:
            result = await self.products.delete_one({
                "category": category,
                "model": model
            })

            return result.deleted_count > 0
        except Exception as error:
            logger.exception("Ошибка при удалении товара '%s' из '%s': %s", model, category, error)
            return False

    async def create_user(self, user_id: int, username: str = None):
        # Keep stored format unchanged (`@username`), but avoid invalid "@None".
        normalized_username = f"@{username}" if username else None
        try:
            await self.users.update_one(
                {"id": user_id},
                {
                    "$set": {"username": normalized_username},
                    "$setOnInsert": {
                        "id": user_id,
                        "cart": [],
                        "created_at": datetime.now()
                    }
                },
                upsert=True
            )
        except Exception as error:
            logger.exception("Ошибка при создании/обновлении пользователя '%s': %s", user_id, error)

    async def get_user_cart(self, user_id: int):
        """Backward-compatible alias for cart retrieval."""
        return await self.get_cart(user_id)

    async def get_cart(self, user_id: int):
        try:
            user = await self.users.find_one({"id": user_id})
            if user and "cart" in user:
                return user["cart"]
        except Exception as error:
            logger.exception("Ошибка при получении корзины пользователя '%s': %s", user_id, error)
        return []

    async def add_to_cart(self, user_id: int, model_name: str, price: int, category_name: str | None = None):
        """Add an item to the user's cart."""
        item_data = {
            "model_name": model_name,
            "price": price
        }
        if category_name:
            item_data["category_name"] = category_name

        try:
            await self.users.update_one(
                {"id": user_id},
                {"$push": {"cart": item_data}},
                upsert=True
            )
        except Exception as error:
            logger.exception(
                "Ошибка при добавлении в корзину пользователя '%s' модели '%s': %s",
                user_id,
                model_name,
                error
            )

    async def clear_cart(self, user_id: int):
        """Remove all cart items for a user."""
        try:
            result = await self.users.update_one(
                {"id": user_id},
                {"$set": {"cart": []}},
                upsert=True
            )
            return result.acknowledged
        except Exception as error:
            logger.exception("Ошибка при очистке корзины пользователя '%s': %s", user_id, error)
            return False

    async def remove_item_from_cart(self, user_id: int, index: int):
        """Remove a cart item by index; return success status."""
        if index < 0:
            return False

        cart_items = await self.get_cart(user_id)
        if index >= len(cart_items):
            return False

        try:
            cart_items.pop(index)
            result = await self.users.update_one(
                {"id": user_id},
                {"$set": {"cart": cart_items}},
                upsert=True
            )
            return result.acknowledged
        except Exception as error:
            logger.exception(
                "Ошибка при удалении позиции корзины пользователя '%s' по индексу '%s': %s",
                user_id,
                index,
                error
            )
            return False


db = Database()
