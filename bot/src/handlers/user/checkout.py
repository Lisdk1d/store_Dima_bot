"""Checkout flow: quantity → delivery address → payment."""

import html
import logging

import httpx
from aiogram import Router, Bot, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.fsm.context import FSMContext
from fluentogram import TranslatorRunner

from src.utils.states import CheckoutProcess
from src.utils.db import db
from src.utils.config import settings
from src.utils.payment_links import sign_payment_token
from src.utils.yookassa_client import create_payment, rubles_to_minor_units
from src.handlers.admin.keyboards import get_payment_methods_keyboard
from src.handlers.user.keyboards import (
    get_cart_actions_keyboard,
    get_cart_empty_keyboard,
    get_item_actions_keyboard,
    get_manager_chat_keyboard,
)
from src.handlers.user.cart_utils import (
    build_cart_text,
    build_manager_order_text,
    build_manager_product_request_text,
    calculate_cart_total,
    format_price_with_ruble,
    notify_managers,
)

router = Router()
logger = logging.getLogger(__name__)

MIN_ADDRESS_LENGTH = 10

PAYMENT_METHOD_LABELS = {
    "card": "payment_method_card",
    "sbp": "payment_method_sbp",
    "cash": "payment_method_cash",
}


def get_payment_label(locale: TranslatorRunner, method: str) -> str:
    label_key = PAYMENT_METHOD_LABELS.get(method)
    if label_key:
        try:
            return locale.get(label_key)
        except Exception:
            logger.exception("Missing payment label for method '%s'", method)
    return method


def validate_address(address: str) -> bool:
    text = (address or "").strip()
    return len(text) >= MIN_ADDRESS_LENGTH


async def _start_online_payment(
    callback: CallbackQuery,
    bot: Bot,
    locale: TranslatorRunner,
    *,
    order_id: int,
    amount_text: str | None,
    manager_fallback_text: str,
) -> None:
    """Create a YooKassa payment and send the customer a "Pay" WebApp button.

    On any failure (online payment disabled, missing amount, YooKassa error) we
    fall back to notifying managers so the order is never silently lost, and the
    customer is told online payment is unavailable. Managers are NOT notified on
    the happy path — that happens from the webhook once payment actually succeeds.
    """
    async def _fallback() -> None:
        await notify_managers(bot, manager_fallback_text, settings.ADMIN_IDS)
        await callback.message.answer(locale.payment_online_unavailable())

    if not settings.online_payment_enabled or not amount_text:
        logger.warning("Online payment unavailable for order %s; falling back to manager", order_id)
        await _fallback()
        return

    try:
        amount_value = rubles_to_minor_units(amount_text)
        async with httpx.AsyncClient() as client:
            payment = await create_payment(
                client=client,
                shop_id=settings.YOOKASSA_SHOP_ID,
                secret_key=settings.YOOKASSA_SECRET_KEY,
                amount_value=amount_value,
                order_id=order_id,
                description=f"Заказ #{order_id}",
                return_url=f"{settings.PAYMENT_PAGE_URL.rstrip('/')}/pay/{order_id}",
                idempotence_key=f"order-{order_id}-create",
            )
        confirmation_url = (payment.get("confirmation") or {}).get("confirmation_url")
        await db.set_payment_provider_id(
            order_id,
            provider="yookassa",
            provider_payment_id=str(payment["id"]),
            details=confirmation_url,
        )
    except Exception as error:
        logger.exception("Failed to start online payment for order %s: %s", order_id, error)
        await _fallback()
        return

    token = sign_payment_token(
        order_id,
        callback.from_user.id,
        secret=settings.PAYMENT_LINK_SECRET,
        ttl_seconds=settings.PAYMENT_LINK_MAX_AGE,
    )
    pay_url = f"{settings.PAYMENT_PAGE_URL.rstrip('/')}/pay/{order_id}?token={token}"
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=locale.payment_pay_button(), web_app=WebAppInfo(url=pay_url))]]
    )
    await callback.message.answer(locale.payment_open_link(), reply_markup=keyboard)


# --- Quantity (single product) ---

@router.message(CheckoutProcess.waiting_for_quantity)
async def process_quantity(message: Message, state: FSMContext, locale: TranslatorRunner):
    raw = (message.text or "").strip()
    if not raw.isdigit() or int(raw) < 1:
        await message.answer(locale.quantity_invalid())
        return

    quantity = int(raw)
    await state.update_data(quantity=quantity)
    await message.answer(locale.delivery_enter_address(), parse_mode="HTML")
    await state.set_state(CheckoutProcess.waiting_for_address)


# --- Delivery address ---

@router.message(CheckoutProcess.waiting_for_address)
async def process_delivery_address(
    message: Message,
    state: FSMContext,
    locale: TranslatorRunner,
):
    address = (message.text or "").strip()
    if not validate_address(address):
        await message.answer(locale.delivery_address_invalid())
        return

    data = await state.get_data()
    checkout_type = data.get("checkout_type", "cart")
    await state.update_data(delivery_address=address)

    if checkout_type == "cart":
        back_callback = "checkout_back_cart"
        prefix = "pay_cart"
    else:
        product_id = data.get("product_id")
        back_callback = f"checkout_back_single|{product_id}"
        prefix = f"pay_single|{product_id}"

    await message.answer(
        locale.payment_choose_method(),
        reply_markup=get_payment_methods_keyboard(
            locale,
            prefix=prefix,
            back_callback=back_callback,
            online_enabled=settings.online_payment_enabled,
        ),
    )
    await state.set_state(CheckoutProcess.waiting_for_payment)


# --- Back from payment to previous step ---

@router.callback_query(F.data == "checkout_back_cart")
async def checkout_back_to_cart(callback: CallbackQuery, state: FSMContext, locale: TranslatorRunner):
    await state.clear()
    if callback.from_user is None:
        await callback.answer()
        return

    cart_items = await db.get_cart(callback.from_user.id)
    cart_text = build_cart_text(cart_items, locale)
    if cart_items:
        await callback.message.edit_text(
            cart_text,
            parse_mode="HTML",
            reply_markup=await get_cart_actions_keyboard(cart_items, locale),
        )
    else:
        await callback.message.edit_text(
            cart_text,
            parse_mode="HTML",
            reply_markup=await get_cart_empty_keyboard(locale),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("checkout_back_single|"))
async def checkout_back_to_product(callback: CallbackQuery, state: FSMContext, locale: TranslatorRunner):
    await state.clear()
    product_id_str = (callback.data or "").replace("checkout_back_single|", "").strip()
    if not product_id_str.isdigit():
        await callback.answer()
        return

    product = await db.get_product_by_id(int(product_id_str))
    if not product:
        await callback.answer(locale.cart_product_not_found(), show_alert=True)
        return

    text = (
        f"📱 <b>{html.escape(str(product.get('model') or locale.unknown_product_name()))}</b>\n\n"
        f"💰 <b>{html.escape(format_price_with_ruble(product.get('price', '')))}</b>\n\n"
        f"{html.escape(str(product.get('description') or ''))}\n"
    )
    markup = await get_item_actions_keyboard(
        model_name=product.get("model", ""),
        price=product.get("price", 0),
        locale=locale,
        product_id=product.get("id"),
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=markup)
    await callback.answer()


# --- Payment stubs ---

@router.callback_query(F.data.startswith("pay_cart|"), CheckoutProcess.waiting_for_payment)
async def pay_cart_stub(callback: CallbackQuery, state: FSMContext, bot: Bot, locale: TranslatorRunner):
    if callback.from_user is None:
        await callback.answer(locale.user_not_defined(), show_alert=True)
        return

    payment_method = (callback.data or "").replace("pay_cart|", "").strip()
    if payment_method not in PAYMENT_METHOD_LABELS:
        await callback.answer()
        return

    await db.create_user(
        user_id=callback.from_user.id,
        username=callback.from_user.username,
    )

    data = await state.get_data()
    delivery_address = data.get("delivery_address", "")
    # Idempotency: drop the payment state up front so a rapid second tap no
    # longer matches this handler and cannot create a duplicate order.
    await state.set_state(None)
    cart_items = await db.get_cart(callback.from_user.id)
    if not cart_items:
        await callback.answer(locale.cart_empty(), show_alert=True)
        await state.clear()
        return

    total = calculate_cart_total(cart_items)
    total_text = f"{total:,}".replace(",", " ") + " ₽" if total else None
    payment_label = get_payment_label(locale, payment_method)

    order_id = await db.create_order(
        user_id=callback.from_user.id,
        cart_items=cart_items,
        payment_method=payment_method,
        total_amount=total_text,
        delivery_address=delivery_address,
        status="pending",
        payment_status="pending",
    )

    if not order_id:
        await callback.answer(locale.cart_checkout_error(), show_alert=True)
        return

    order_text = build_manager_order_text(
        cart_items=cart_items,
        locale=locale,
        full_name=callback.from_user.full_name,
        username=callback.from_user.username,
        user_id=callback.from_user.id,
    )
    order_text += f"\n\n📍 <b>Адрес:</b> {html.escape(delivery_address)}"
    order_text += f"\n💳 <b>Оплата:</b> {html.escape(payment_label)}"
    order_text += f"\n🆔 <b>Заказ:</b> <code>#{order_id}</code>"

    # The cart has moved into the order's items — empty it regardless of method.
    await db.clear_cart(callback.from_user.id)
    await state.clear()
    await callback.answer()

    if payment_method == "cash":
        # Cash: the manager notification IS the confirmation (no money moves online).
        if await notify_managers(bot, order_text, settings.ADMIN_IDS) == 0:
            await callback.answer(locale.cart_checkout_error(), show_alert=True)
            return
        await callback.message.answer(
            locale.payment_order_confirmed(method=payment_label),
            reply_markup=await get_manager_chat_keyboard(locale),
        )
    else:
        # Card/SBP: create a YooKassa payment and send a "Pay" button. Managers are
        # notified later, from the webhook, once payment actually succeeds.
        await _start_online_payment(
            callback, bot, locale,
            order_id=order_id, amount_text=total_text, manager_fallback_text=order_text,
        )


@router.callback_query(F.data.startswith("pay_single|"), CheckoutProcess.waiting_for_payment)
async def pay_single_stub(callback: CallbackQuery, state: FSMContext, bot: Bot, locale: TranslatorRunner):
    if callback.from_user is None:
        await callback.answer(locale.user_not_defined(), show_alert=True)
        return

    payload = (callback.data or "").replace("pay_single|", "")
    parts = payload.split("|", maxsplit=1)
    if len(parts) != 2:
        await callback.answer(locale.buy_request_error(), show_alert=True)
        return

    product_id_str, payment_method = parts[0].strip(), parts[1].strip()
    if not product_id_str.isdigit() or payment_method not in PAYMENT_METHOD_LABELS:
        await callback.answer(locale.buy_request_error(), show_alert=True)
        return

    await db.create_user(
        user_id=callback.from_user.id,
        username=callback.from_user.username,
    )

    data = await state.get_data()
    delivery_address = data.get("delivery_address", "")
    quantity = int(data.get("quantity", 1))
    # Idempotency: drop the payment state up front so a rapid second tap no
    # longer matches this handler and cannot create a duplicate order.
    await state.set_state(None)

    product = await db.get_product_by_id(int(product_id_str))
    if not product:
        await callback.answer(locale.cart_product_not_found(), show_alert=True)
        await state.clear()
        return

    model_name = product.get("model", "")
    cart_item = [{
        "model_name": model_name,
        "price": product.get("price", ""),
        "category_name": product.get("category"),
        "quantity": quantity,
    }]
    price_text = format_price_with_ruble(product.get("price", ""))
    payment_label = get_payment_label(locale, payment_method)

    order_id = await db.create_order(
        user_id=callback.from_user.id,
        cart_items=cart_item,
        payment_method=payment_method,
        total_amount=price_text,
        delivery_address=delivery_address,
        status="pending",
        payment_status="pending",
    )

    if not order_id:
        await callback.answer(locale.buy_request_error(), show_alert=True)
        return

    order_text = build_manager_product_request_text(
        locale=locale,
        full_name=callback.from_user.full_name,
        username=callback.from_user.username,
        user_id=callback.from_user.id,
        model_name=model_name,
        price=product.get("price", ""),
    )
    order_text += f"\n📦 <b>Количество:</b> {quantity}"
    order_text += f"\n📍 <b>Адрес:</b> {html.escape(delivery_address)}"
    order_text += f"\n💳 <b>Оплата:</b> {html.escape(payment_label)}"
    order_text += f"\n🆔 <b>Заказ:</b> <code>#{order_id}</code>"

    await state.clear()
    await callback.answer()

    if payment_method == "cash":
        if await notify_managers(bot, order_text, settings.ADMIN_IDS) == 0:
            await callback.answer(locale.buy_request_error(), show_alert=True)
            return
        await callback.message.answer(
            locale.payment_order_confirmed(method=payment_label),
            reply_markup=await get_manager_chat_keyboard(locale),
        )
    else:
        await _start_online_payment(
            callback, bot, locale,
            order_id=order_id, amount_text=price_text, manager_fallback_text=order_text,
        )
