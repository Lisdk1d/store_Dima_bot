from src.utils.config import settings
from motor.motor_asyncio import AsyncIOMotorClient
import logging
from datetime import datetime


class Database:
    def __init__(self):

        self.client = AsyncIOMotorClient(
            settings.MONGO_URL)
        self.db = self.client[settings.DB_NAME]

        self.users = self.db.users
        self.products = self.db.products

    async def get_unique_categories(self):

        return await self.products.distinct("category", {"stock": {"$gt": 0}})

    async def get_models_by_category(self, category: str):

        return await self.products.distinct("model", {"category": category, "stock": {"$gt": 0}})

    async def get_product_details(self, model: str):

        return await self.products.find_one({"model": model, "stock": {"$gt": 0}})

    async def check_connection(self):

        try:
            await self.client.admin.command('ping')
            print("✅ Успешное подключение к MongoDB")

        except Exception as e:
            print(f"❌ Ошибка подключения к MongoDB: {e}")

    async def add_product(self, category: str, model: str, price: int, description: str, photo_id: str, stock: int = 1):
        document = {
            "category": category,
            "model": model,
            "description": description,
            "price": price,
            "photo_id": photo_id,
            "stock": stock,
            "created_at": datetime.now()
        }
        result = await self.products.insert_one(document)
        return result.inserted_id

    async def delete_model(self, category: str, model: str):
        try:
            result = await self.products.delete_one({
                "category": category,
                "model": model
            })

            return result.deleted_count > 0
        except Exception as e:
            logging.error(f"Ошибка при удалении товара: {e}")
            return False

    async def create_user(self, user_id: int, username: str = None):
        await self.users.update_one(
            {"id": user_id},
            {
                "$set": {"username": "@" + username},
                "$setOnInsert": {
                    "id": user_id,
                    "cart": [],
                    "created_at": datetime.now()
                }
            },
            upsert=True
        )

    async def get_user_cart(self, user_id: int):
        user = await self.users.find_one({"id": user_id})
        if user and "cart" in user:
            return user["cart"]
        return []

    async def add_to_cart(self, user_id: int, model: str, price: int):

        item_data = {
            "model": model,
            "price": price
        }

        await self.users.update_one(
            {"id": user_id},
            {"$push": {"cart": item_data}},
            upsert=True
        )


db = Database()
