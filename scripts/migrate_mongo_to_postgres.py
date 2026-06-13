"""
One-time migration script: MongoDB -> PostgreSQL.

Usage:
    MONGO_URL=mongodb://... python scripts/migrate_mongo_to_postgres.py

Requires motor and pymongo (install separately if needed):
    pip install motor pymongo
"""

import asyncio
import os
import sys

# Allow imports from bot package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bot"))

from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore
from src.utils.db import db
from src.models import init_db


async def migrate() -> None:
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME", "gorba_bot")
    if not mongo_url:
        print("Set MONGO_URL environment variable")
        sys.exit(1)

    client = AsyncIOMotorClient(mongo_url)
    mongo_db = client[db_name]

    await init_db()

    products = await mongo_db.products.find({}).to_list(length=None)
    for doc in products:
        await db.add_product(
            category=doc.get("category", ""),
            model=doc.get("model", ""),
            price=str(doc.get("price", "")),
            description=doc.get("description", ""),
            photo_id=doc.get("photo_id", ""),
            stock=int(doc.get("stock", 1)),
        )

    users = await mongo_db.users.find({}).to_list(length=None)
    for user in users:
        await db.create_user(user_id=user["id"], username=(user.get("username") or "").lstrip("@") or None)
        for item in user.get("cart", []):
            await db.add_to_cart(
                user_id=user["id"],
                model_name=item.get("model_name") or item.get("model", ""),
                price=str(item.get("price", "")),
                category_name=item.get("category_name"),
            )

    print(f"Migrated {len(products)} products and {len(users)} users")
    client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
