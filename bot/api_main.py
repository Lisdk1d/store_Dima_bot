"""FastAPI admin backend."""

import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text

from src.utils.config import settings
from src.utils.db import db
from src.models import init_db
from src.models.base import engine

logger = logging.getLogger(__name__)


class ProductCreate(BaseModel):
    category: str
    model: str
    description: str
    price: str
    photo_id: str = ""
    stock: int = 1


class ProductUpdate(BaseModel):
    category: str | None = None
    model: str | None = None
    description: str | None = None
    price: str | None = None
    photo_id: str | None = None
    stock: int | None = None


class OrderItemResponse(BaseModel):
    model_name: str
    price: str
    category_name: str | None = None
    quantity: int = 1


class OrderResponse(BaseModel):
    id: int
    user_id: int
    username: str | None = None
    status: str
    payment_method: str | None = None
    total_amount: str | None = None
    delivery_address: str | None = None
    delivery_fee: str | None = None
    created_at: str | None = None
    items: list[OrderItemResponse]


def _extract_api_key(
    x_api_key: str | None,
    authorization: str | None,
) -> str | None:
    if x_api_key:
        return x_api_key
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


async def verify_api_key(
    x_api_key: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    token = _extract_api_key(x_api_key, authorization)
    if token != settings.API_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        await init_db()
    except Exception as error:
        logger.critical("API cannot start without database: %s", error)
        raise
    logger.info("Admin API started")
    yield


app = FastAPI(title="Shop Admin API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)
logger.info("CORS allowed origins: %s", settings.CORS_ORIGINS)


@app.get("/health")
async def health():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as error:
        logger.error("Health check DB error: %s", error)
        raise HTTPException(status_code=503, detail="Database unavailable") from error


@app.get("/api/stats", dependencies=[Depends(verify_api_key)])
async def get_stats():
    return {
        "products_count": await db.get_products_count(),
        "orders_count": await db.get_orders_count(),
        "categories_count": len(await db.get_all_categories()),
    }


@app.get("/api/products", dependencies=[Depends(verify_api_key)])
async def list_products():
    return await db.get_all_products()


@app.get("/api/categories", dependencies=[Depends(verify_api_key)])
async def list_categories():
    return await db.get_all_categories()


@app.get("/api/orders", response_model=list[OrderResponse], dependencies=[Depends(verify_api_key)])
async def list_orders(limit: int = 100):
    return await db.get_all_orders(limit=limit)


@app.post("/api/products", dependencies=[Depends(verify_api_key)])
async def create_product(payload: ProductCreate):
    logger.info("API create_product: model=%s category=%s", payload.model, payload.category)
    product_id = await db.add_product(
        category=payload.category,
        model=payload.model,
        description=payload.description,
        price=payload.price,
        photo_id=payload.photo_id,
        stock=payload.stock,
    )
    if not product_id:
        raise HTTPException(status_code=400, detail="Failed to create product")
    return {"id": product_id}


@app.patch("/api/products/{model_name}", dependencies=[Depends(verify_api_key)])
async def update_product(model_name: str, payload: ProductUpdate):
    updates = payload.model_dump(exclude_unset=True)
    success = await db.update_product(model_name, **updates)
    if not success:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"status": "updated"}


@app.delete("/api/products/{model_name}", dependencies=[Depends(verify_api_key)])
async def delete_product(model_name: str):
    success = await db.delete_model_by_name(model_name)
    if not success:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"status": "deleted"}


@app.delete("/api/categories/{category_name}", dependencies=[Depends(verify_api_key)])
async def delete_category(category_name: str):
    count = await db.delete_category(category_name)
    if count == 0:
        raise HTTPException(status_code=404, detail="Category not found")
    return {"deleted_count": count}
