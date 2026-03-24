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

    async def check_connection(self):

        try:
            await self.client.admin.command('ping')
            print("✅ Успешное подключение к MongoDB")

            test_col = self.db["test_connection"]
            await test_col.insert_one({"status": "ready", "version": 1.0})
            logging.info("✅ Тестовая запись успешно создана")

        except Exception as e:
            print(f"❌ Ошибка подключения к MongoDB: {e}")

    async def add_product(self, description: str, photo_id: str, user_id: int):
        document = {
            "user_id": user_id,
            "description": description,
            "photo_id": photo_id,
            "created_at": datetime.now()
        }
        result = await self.products.insert_one(document)
        return result.inserted_id


db = Database()
