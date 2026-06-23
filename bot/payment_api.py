"""Customer-facing payment page + YooKassa webhook (no admin auth).

Separate process/container from the admin API so the public payment surface is
isolated. The payment page is gated by a per-order signed token (not initData,
since customers are not admins). The webhook is NOT signed by YooKassa, so its
body is never trusted: we re-fetch the authoritative payment from YooKassa and
act only on that.
"""

import html
import json
import logging
from contextlib import asynccontextmanager

import httpx
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import text

from src.utils.config import settings
from src.utils.db import db
from src.utils.logging_config import configure_logging
from src.utils.payment_links import PaymentLinkError, verify_payment_token
from src.utils.yookassa_client import YooKassaError, get_payment, yookassa_amount_matches_order
from src.handlers.user.cart_utils import notify_managers
from src.models import init_db
from src.models.base import engine

configure_logging()
logger = logging.getLogger(__name__)

PROVIDER = "yookassa"

# Notification-only bot client (lazy session, closed on shutdown).
_bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        await init_db()
    except Exception as error:
        logger.critical("Payment service cannot start without database: %s", error)
        raise
    logger.info("Payment page service started")
    yield
    await _bot.session.close()


app = FastAPI(title="Gorba Payment Page", version="1.0.0", lifespan=lifespan)


def _page(title: str, body_html: str, status_code: int = 200) -> HTMLResponse:
    document = (
        "<!doctype html><html lang='ru'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{html.escape(title)}</title></head>"
        "<body style='font-family:system-ui,sans-serif;max-width:480px;margin:40px auto;padding:0 16px;text-align:center'>"
        f"{body_html}</body></html>"
    )
    return HTMLResponse(content=document, status_code=status_code)


@app.get("/health")
async def health():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as error:
        logger.error("Health check DB error: %s", error)
        raise HTTPException(status_code=503, detail="Database unavailable") from error


@app.get("/pay/{order_id}", response_class=HTMLResponse)
async def payment_page(order_id: int, token: str = Query(...)):
    if not settings.online_payment_enabled:
        raise HTTPException(status_code=503, detail="online payment is not configured")

    try:
        claims = verify_payment_token(token, secret=settings.PAYMENT_LINK_SECRET)
    except PaymentLinkError:
        return _page("Ссылка недействительна", "<h2>Ссылка недействительна или устарела</h2>"
                     "<p>Оформите заказ заново в боте.</p>", status_code=400)

    if claims["order_id"] != order_id:
        return _page("Ссылка недействительна", "<h2>Ссылка недействительна</h2>", status_code=400)

    order = await db.get_order_by_id(order_id)
    if not order or order.get("user_id") != claims["user_id"]:
        return _page("Заказ не найден", "<h2>Заказ не найден</h2>", status_code=404)

    payment = await db.get_payment_for_order(order_id)
    if payment and payment.get("status") == "succeeded":
        return _page("Заказ оплачен", f"<h2>✅ Заказ #{order_id} оплачен</h2>"
                     "<p>Менеджер свяжется с вами по доставке.</p>")

    confirmation_url = (payment or {}).get("details") or ""
    total = html.escape(str(order.get("total_amount") or "—"))
    if not confirmation_url.startswith("https://"):
        return _page("Оплата недоступна", "<h2>Оплата временно недоступна</h2>"
                     "<p>Попробуйте позже или свяжитесь с менеджером.</p>", status_code=502)

    return _page(
        f"Оплата заказа #{order_id}",
        f"<h2>Заказ #{order_id}</h2><p>Сумма к оплате: <b>{total}</b></p>"
        f"<p><a href='{html.escape(confirmation_url)}' "
        "style='display:inline-block;padding:14px 28px;background:#5b51d8;color:#fff;"
        "border-radius:10px;text-decoration:none;font-weight:600'>Перейти к оплате</a></p>",
    )


async def _notify_paid(order: dict) -> None:
    """Tell the customer and managers that an order has been paid."""
    order_id = order["id"]
    try:
        await _bot.send_message(
            order["user_id"],
            f"✅ Оплата получена! Заказ <code>#{order_id}</code> оплачен.\n"
            "Менеджер свяжется с вами по доставке.",
        )
    except Exception as error:
        logger.exception("Failed to notify customer for order %s: %s", order_id, error)

    manager_text = (
        f"💰 <b>Оплачен заказ</b> <code>#{order_id}</code>\n"
        f"Покупатель: <code>{order.get('user_id')}</code>\n"
        f"Сумма: {html.escape(str(order.get('total_amount') or '—'))}\n"
        f"Адрес: {html.escape(str(order.get('delivery_address') or '—'))}"
    )
    await notify_managers(_bot, manager_text, settings.ADMIN_IDS)


async def reconcile_payment(payment: dict) -> str:
    """Apply an authoritative YooKassa payment object to its order.

    Returns a short status string ("paid"/"canceled"/"pending"/"ignored"/
    "amount_mismatch") — pure enough to unit-test with fakes for db/_bot.
    """
    payment_id = str(payment.get("id") or "")
    status = payment.get("status")
    metadata = payment.get("metadata") or {}
    order_hint = metadata.get("order_id")

    order = None
    if order_hint and str(order_hint).isdigit():
        order = await db.get_order_by_id(int(order_hint))
    cross = await db.get_order_by_provider_payment_id(PROVIDER, payment_id)
    if order and cross and order["id"] != cross["id"]:
        logger.error("Order mismatch for payment %s (%s vs %s)", payment_id, order["id"], cross["id"])
        return "ignored"
    order = order or cross
    if not order:
        logger.error("No order found for payment %s", payment_id)
        return "ignored"

    if status == "succeeded":
        amount_value = (payment.get("amount") or {}).get("value")
        if not yookassa_amount_matches_order(amount_value, order.get("total_amount")):
            logger.warning(
                "Amount mismatch for order %s: yookassa=%s order=%s",
                order["id"], amount_value, order.get("total_amount"),
            )
            return "amount_mismatch"
        await db.update_payment_status(order["id"], status="succeeded", order_status="confirmed")
        await _notify_paid(order)
        return "paid"

    if status == "canceled":
        await db.update_payment_status(order["id"], status="canceled", order_status="cancelled")
        return "canceled"

    return "pending"


@app.post("/webhooks/yookassa")
async def yookassa_webhook(request: Request):
    if not settings.online_payment_enabled:
        raise HTTPException(status_code=503, detail="online payment is not configured")

    try:
        data = json.loads(await request.body() or b"{}")
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail="invalid JSON") from error

    obj = data.get("object") or {}
    payment_id = str(obj.get("id") or "")
    event = str(data.get("event") or "")
    if not payment_id or not event:
        raise HTTPException(status_code=400, detail="missing event/object id")

    # Re-fetch the authoritative payment FIRST — the webhook body is unsigned and
    # never trusted. (A failed fetch returns 5xx so YooKassa retries, and we have
    # not yet consumed the idempotency key, so the retry can still be processed.)
    try:
        async with httpx.AsyncClient() as client:
            payment = await get_payment(
                client=client,
                shop_id=settings.YOOKASSA_SHOP_ID,
                secret_key=settings.YOOKASSA_SECRET_KEY,
                payment_id=payment_id,
            )
    except YooKassaError as error:
        logger.error("YooKassa verification fetch failed for %s: %s", payment_id, error)
        raise HTTPException(status_code=502, detail="verification failed") from error

    # Idempotency: consume the key only after a successful fetch, just before we
    # mutate state, so a repeated delivery is a no-op.
    order_hint = (payment.get("metadata") or {}).get("order_id")
    order_id_int = int(order_hint) if order_hint and str(order_hint).isdigit() else None
    if not await db.record_payment_event(PROVIDER, f"{payment_id}:{event}", order_id_int):
        return JSONResponse({"status": "duplicate"})

    result = await reconcile_payment(payment)
    return JSONResponse({"status": result})
