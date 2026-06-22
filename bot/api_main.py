"""FastAPI admin backend."""

import json
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import text

from src.utils.config import settings
from src.utils.auth import AdminPrincipal, require_admin
from src.utils.db import db
from src.utils.payments import amounts_match, verify_webhook_signature
from src.utils.request_context import get_request_id, new_request_id
from src.models import init_db
from src.models.base import engine

logger = logging.getLogger(__name__)


class ProductCreate(BaseModel):
    category: str = Field(min_length=1, max_length=255)
    model: str = Field(min_length=1, max_length=512)
    description: str = Field(min_length=1, max_length=4000)
    price: str = Field(min_length=1, max_length=128)
    photo_id: str = Field(default="", max_length=512)
    stock: int = Field(default=1, ge=0, le=1_000_000)


class ProductUpdate(BaseModel):
    category: str | None = Field(default=None, min_length=1, max_length=255)
    model: str | None = Field(default=None, min_length=1, max_length=512)
    description: str | None = Field(default=None, min_length=1, max_length=4000)
    price: str | None = Field(default=None, min_length=1, max_length=128)
    photo_id: str | None = Field(default=None, max_length=512)
    stock: int | None = Field(default=None, ge=0, le=1_000_000)


class OrderItemResponse(BaseModel):
    model_name: str
    price: str
    category_name: str | None = None
    quantity: int = 1


class OrderItemUpdate(BaseModel):
    model_name: str = Field(min_length=1, max_length=512)
    price: str = Field(min_length=1, max_length=128)
    category_name: str | None = Field(default=None, max_length=255)
    quantity: int = Field(default=1, ge=1, le=100_000)


class OrderUpdate(BaseModel):
    status: str | None = Field(default=None, max_length=32)
    payment_method: str | None = Field(default=None, max_length=64)
    delivery_address: str | None = Field(default=None, max_length=4000)
    delivery_fee: str | None = Field(default=None, max_length=128)
    comment: str | None = Field(default=None, max_length=4000)
    total_amount: str | None = Field(default=None, max_length=128)
    items: list[OrderItemUpdate] | None = None


class OrderResponse(BaseModel):
    id: int
    user_id: int
    username: str | None = None
    status: str
    payment_method: str | None = None
    total_amount: str | None = None
    delivery_address: str | None = None
    delivery_fee: str | None = None
    comment: str | None = None
    created_at: str | None = None
    items: list[OrderItemResponse]


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


@app.middleware("http")
async def assign_request_id(request: Request, call_next):
    request_id = new_request_id()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


async def _audit(
    admin: AdminPrincipal,
    action: str,
    object_type: str | None = None,
    object_id: str | int | None = None,
    detail: str | None = None,
) -> None:
    await db.add_audit_log(
        actor_id=admin.admin_id,
        actor_username=admin.username,
        action=action,
        object_type=object_type,
        object_id=object_id,
        detail=detail,
        request_id=get_request_id(),
    )


@app.get("/health")
async def health():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as error:
        logger.error("Health check DB error: %s", error)
        raise HTTPException(status_code=503, detail="Database unavailable") from error


@app.get("/api/stats", dependencies=[Depends(require_admin)])
async def get_stats():
    return {
        "products_count": await db.get_products_count(),
        "orders_count": await db.get_orders_count(),
        "categories_count": len(await db.get_all_categories()),
    }


@app.get("/api/products", dependencies=[Depends(require_admin)])
async def list_products():
    return await db.get_all_products()


@app.get("/api/categories", dependencies=[Depends(require_admin)])
async def list_categories():
    return await db.get_all_categories()


@app.get("/api/orders", response_model=list[OrderResponse], dependencies=[Depends(require_admin)])
async def list_orders(limit: int = Query(default=100, ge=1, le=500)):
    return await db.get_all_orders(limit=limit)


@app.patch("/api/orders/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: int,
    payload: OrderUpdate,
    admin: AdminPrincipal = Depends(require_admin),
):
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    success = await db.update_order(order_id, **updates)
    if not success:
        raise HTTPException(status_code=404, detail="Order not found")
    # Log changed field NAMES only — values may contain personal data.
    await _audit(admin, "order.update", "order", order_id, "fields=" + ",".join(sorted(updates)))
    order = await db.get_order_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.delete("/api/orders/{order_id}")
async def delete_order(order_id: int, admin: AdminPrincipal = Depends(require_admin)):
    success = await db.delete_order(order_id)
    if not success:
        raise HTTPException(status_code=404, detail="Order not found")
    await _audit(admin, "order.delete", "order", order_id)
    return {"status": "deleted"}


@app.post("/api/products")
async def create_product(payload: ProductCreate, admin: AdminPrincipal = Depends(require_admin)):
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
    await _audit(admin, "product.create", "product", payload.model)
    return {"id": product_id}


@app.patch("/api/products/{model_name}")
async def update_product(
    model_name: str,
    payload: ProductUpdate,
    admin: AdminPrincipal = Depends(require_admin),
):
    updates = payload.model_dump(exclude_unset=True)
    success = await db.update_product(model_name, **updates)
    if not success:
        raise HTTPException(status_code=404, detail="Product not found")
    await _audit(admin, "product.update", "product", model_name, "fields=" + ",".join(sorted(updates)))
    return {"status": "updated"}


@app.delete("/api/products/{model_name}")
async def delete_product(model_name: str, admin: AdminPrincipal = Depends(require_admin)):
    success = await db.delete_model_by_name(model_name)
    if not success:
        raise HTTPException(status_code=404, detail="Product not found")
    await _audit(admin, "product.delete", "product", model_name)
    return {"status": "deleted"}


@app.delete("/api/categories/{category_name}")
async def delete_category(category_name: str, admin: AdminPrincipal = Depends(require_admin)):
    count = await db.delete_category(category_name)
    if count == 0:
        raise HTTPException(status_code=404, detail="Category not found")
    await _audit(admin, "category.delete", "category", category_name, f"deleted_count={count}")
    return {"deleted_count": count}


@app.post("/webhooks/payment/{provider}")
async def payment_webhook(
    provider: str,
    request: Request,
    x_signature: str | None = Header(default=None),
):
    """Payment-provider webhook: signature-verified, idempotent, amount-checked.

    SCAFFOLD: the signature header name and JSON shape are provider-specific and
    must be finalized when a provider is chosen. The endpoint is disabled until
    PAYMENT_WEBHOOK_SECRET is set, and rejects any request without a valid HMAC.
    """
    if not settings.PAYMENT_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Payment webhook not configured")

    body = await request.body()
    if not verify_webhook_signature(body, x_signature, settings.PAYMENT_WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        data = json.loads(body or b"{}")
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail="Invalid JSON") from error

    event_id = str(data.get("event_id") or data.get("id") or "")
    if not event_id:
        raise HTTPException(status_code=400, detail="Missing event id")
    order_id = data.get("order_id")

    # Idempotency: a repeated delivery of the same event is a no-op.
    if not await db.record_payment_event(provider, event_id, order_id):
        return {"status": "duplicate"}

    # Never trust the amount from the payload — verify against the stored order.
    if order_id is not None:
        order = await db.get_order_by_id(int(order_id))
        if order and not amounts_match(data.get("amount"), order.get("total_amount")):
            logger.warning("Payment amount mismatch for order %s (provider=%s)", order_id, provider)
            raise HTTPException(status_code=400, detail="Amount mismatch")

    # TODO(provider): map provider status -> order/payment state once chosen.
    logger.info("Payment event accepted: provider=%s event=%s order=%s", provider, event_id, order_id)
    return {"status": "accepted"}
