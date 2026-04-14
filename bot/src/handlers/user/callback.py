import logging
import re

from aiogram import Router, Bot, F
from aiogram.types import CallbackQuery
from fluentogram import TranslatorRunner
from src.handlers.user.keyboards import (
    get_start_kb,
    get_item_actions_keyboard,
    get_cart_actions_keyboard,
    get_cart_empty_keyboard,
    get_info_back_keyboard,
    get_manager_chat_keyboard,
)
from src.utils.db import db
from src.utils.config import settings
from .cart_utils import build_cart_text, build_manager_order_text, build_manager_product_request_text


from .keyboards import get_assortment_keyboard, get_models_keyboard


router = Router()
logger = logging.getLogger(__name__)

def _parse_add_to_cart_callback(callback_data: str) -> str | None:
    """Parse callback payload formats:
    - add_to_cart|<model_name>
    - add_to_cart|<model_name>|<legacy_price>
    """
    if not callback_data.startswith("add_to_cart|"):
        return None

    payload = callback_data[len("add_to_cart|"):].strip()
    if not payload:
        return None

    # Backward compatibility: older payload may include '|price'.
    model_name = payload.split("|", maxsplit=1)[0].strip()
    return model_name or None


def _parse_buy_product_callback(callback_data: str) -> str | None:
    if not callback_data.startswith("buy_product|"):
        return None
    model_name = callback_data[len("buy_product|"):].strip()
    return model_name or None


@router.callback_query(lambda c: c.data == "reviews")
async def show_reviews(callback: CallbackQuery,
                       bot: Bot,
                       locale: TranslatorRunner):
    await callback.message.answer(
        locale.reviews_callback(),
        reply_markup=await get_info_back_keyboard(locale)
    )


@router.callback_query(lambda c: c.data == "address")
async def show_adrdress(callback: CallbackQuery,
                        bot: Bot,
                        locale: TranslatorRunner):
    await callback.message.answer(
        locale.locale_callback(),
        reply_markup=await get_info_back_keyboard(locale)
    )


@router.callback_query(lambda c: c.data == "delivery")
async def show_delivery(callback: CallbackQuery,
                        bot: Bot,
                        locale: TranslatorRunner):
    await callback.message.answer(
        locale.trans_callback(),
        reply_markup=await get_info_back_keyboard(locale)
    )


@router.callback_query(F.data == "asort")
async def show_categories(callback: CallbackQuery,
                          locale: TranslatorRunner):
    categories = await db.get_unique_categories()

    if not categories:
        await callback.message.edit_text(locale.no_products_available())
        return

    await callback.message.edit_text(
        text=locale.choose_category(),
        reply_markup=await get_assortment_keyboard(categories, locale)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat_"))
async def show_models(callback: CallbackQuery, locale: TranslatorRunner):
    callback_data = callback.data or ""
    category = callback_data.replace("cat_", "").strip()

    models = await db.get_models_by_category(category)

    if not models:
        await callback.message.answer(locale.no_products_available())
        await callback.answer()
        return

    await callback.message.answer(
        text=locale.choose_model(category=category),
        reply_markup=await get_models_keyboard(category, models, locale)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("model_"))
async def show_product_card(callback: CallbackQuery, locale: TranslatorRunner):
    callback_data = callback.data or ""
    model_name = callback_data.replace("model_", "").strip()

    product = await db.get_product_details(model_name)

    if not product:
        await callback.answer(locale.product_unavailable(), show_alert=True)
        return

    text = (
        f"📱 <b>{product.get('model', locale.unknown_product_name())}</b>\n\n"
        f"💰 <b>{product.get('price', locale.unknown_product_price())}</b>\n\n"
        f"{product.get('description', locale.unknown_product_description())}\n\n"
    )

    try:
        if product.get("photo_id"):
            await callback.message.answer_photo(
                photo=product["photo_id"],
                caption=text,
                reply_markup=await get_item_actions_keyboard(
                    model_name=product.get("model", ""),
                    price=product.get("price", 0),
                    locale=locale
                ),
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                text=text,
                reply_markup=await get_item_actions_keyboard(
                    model_name=product.get("model", ""),
                    price=product.get("price", 0),
                    locale=locale
                ),
                parse_mode="HTML"
            )
    except Exception as error:
        logger.exception("Ошибка при отправке карточки товара '%s': %s", model_name, error)
        await callback.answer(locale.product_display_error(), show_alert=True)

    await callback.answer()


@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery, locale: TranslatorRunner):
    await callback.message.edit_text(
        text=locale.welcome_text(name=callback.from_user.full_name),
        reply_markup=get_start_kb(locale)
    )


@router.callback_query(F.data == "del_card_with_exit")
async def back_to_models_list(callback: CallbackQuery,
                              locale: TranslatorRunner):
    await callback.message.delete()


@router.callback_query(F.data.startswith("add_to_cart|"))
async def add_item_to_cart(callback: CallbackQuery, locale: TranslatorRunner):
    if callback.from_user is None:
        await callback.answer(locale.user_not_defined(), show_alert=True)
        return

    callback_data = callback.data or ""
    model_name = _parse_add_to_cart_callback(callback_data)
    if not model_name:
        await callback.answer(locale.cart_add_failed(), show_alert=True)
        return

    product = await db.get_product_details(model_name)
    if not product:
        await callback.answer(locale.cart_product_not_found(), show_alert=True)
        return

    raw_price = product.get("price", 0)
    if isinstance(raw_price, (int, float)):
        price = int(raw_price)
    else:
        # Parse first numeric chunk to avoid merging ranges like "80000/120000".
        first_price_match = re.search(r"\d[\d\s,\.]*", str(raw_price))
        if not first_price_match:
            await callback.answer(locale.invalid_product_price(), show_alert=True)
            return

        normalized_price = re.sub(r"[^\d]", "", first_price_match.group(0))
        if not normalized_price:
            await callback.answer(locale.invalid_product_price(), show_alert=True)
            return

        price = int(normalized_price)

    await db.add_to_cart(
        user_id=callback.from_user.id,
        model_name=model_name,
        price=price,
        category_name=product.get("category")
    )
    await callback.answer(locale.cart_item_added())


@router.callback_query(F.data == "cart_show")
async def show_cart_from_menu(callback: CallbackQuery, locale: TranslatorRunner):
    if callback.from_user is None:
        await callback.answer(locale.user_not_defined(), show_alert=True)
        return

    cart_items = await db.get_cart(callback.from_user.id)
    cart_text = build_cart_text(cart_items, locale)
    if cart_items:
        await callback.message.edit_text(
            cart_text,
            parse_mode="HTML",
            reply_markup=await get_cart_actions_keyboard(cart_items, locale)
        )
    else:
        await callback.message.edit_text(
            cart_text,
            parse_mode="HTML",
            reply_markup=await get_cart_empty_keyboard(locale)
        )

    await callback.answer()


@router.callback_query(F.data == "cart_clear")
async def clear_cart(callback: CallbackQuery, locale: TranslatorRunner):
    if callback.from_user is None:
        await callback.answer(locale.user_not_defined(), show_alert=True)
        return

    await db.clear_cart(callback.from_user.id)
    await callback.message.edit_text(
        locale.cart_empty(),
        parse_mode="HTML",
        reply_markup=await get_cart_empty_keyboard(locale)
    )
    await callback.answer(locale.cart_cleared())


@router.callback_query(F.data.startswith("cart_remove|"))
async def remove_cart_item(callback: CallbackQuery, locale: TranslatorRunner):
    if callback.from_user is None:
        await callback.answer(locale.user_not_defined(), show_alert=True)
        return

    callback_data = callback.data or ""
    try:
        _, raw_index = callback_data.split("|", maxsplit=1)
        item_index = int(raw_index)
    except (ValueError, TypeError):
        await callback.answer(locale.cart_index_error(), show_alert=True)
        return

    removed = await db.remove_item_from_cart(callback.from_user.id, item_index)
    if not removed:
        await callback.answer(locale.cart_remove_failed(), show_alert=True)
        return

    updated_cart = await db.get_cart(callback.from_user.id)
    cart_text = build_cart_text(updated_cart, locale)
    if updated_cart:
        await callback.message.edit_text(
            cart_text,
            parse_mode="HTML",
            reply_markup=await get_cart_actions_keyboard(updated_cart, locale)
        )
    else:
        await callback.message.edit_text(
            cart_text,
            parse_mode="HTML",
            reply_markup=await get_cart_empty_keyboard(locale)
        )

    await callback.answer(locale.cart_item_removed())


@router.callback_query(F.data == "cart_checkout")
async def checkout_cart(callback: CallbackQuery, bot: Bot, locale: TranslatorRunner):
    if callback.from_user is None:
        await callback.answer(locale.user_not_defined(), show_alert=True)
        return

    cart_items = await db.get_cart(callback.from_user.id)
    if not cart_items:
        await callback.answer(locale.cart_empty(), show_alert=True)
        return

    order_text = build_manager_order_text(
        cart_items=cart_items,
        locale=locale,
        full_name=callback.from_user.full_name,
        username=callback.from_user.username,
        user_id=callback.from_user.id,
    )

    sent_count = 0
    for manager_id in settings.ADMIN_IDS:
        try:
            await bot.send_message(chat_id=manager_id, text=order_text, parse_mode="HTML")
            sent_count += 1
        except Exception as error:
            logger.exception("Failed to send order to manager '%s': %s", manager_id, error)

    if sent_count == 0:
        await callback.answer(locale.cart_checkout_error(), show_alert=True)
        return

    await callback.answer(locale.cart_checkout_sent(), show_alert=True)
    await callback.message.answer(
        locale.cart_checkout_sent(),
        reply_markup=await get_manager_chat_keyboard(locale)
    )


@router.callback_query(F.data.startswith("buy_product|"))
async def checkout_product_from_card(callback: CallbackQuery, bot: Bot, locale: TranslatorRunner):
    if callback.from_user is None:
        await callback.answer(locale.user_not_defined(), show_alert=True)
        return

    callback_data = callback.data or ""
    model_name = _parse_buy_product_callback(callback_data)
    if not model_name:
        await callback.answer(locale.buy_request_error(), show_alert=True)
        return

    product = await db.get_product_details(model_name)
    if not product:
        await callback.answer(locale.cart_product_not_found(), show_alert=True)
        return

    order_text = build_manager_product_request_text(
        locale=locale,
        full_name=callback.from_user.full_name,
        username=callback.from_user.username,
        user_id=callback.from_user.id,
        model_name=product.get("model", model_name),
        price=product.get("price", locale.unknown_product_price()),
    )

    sent_count = 0
    for manager_id in settings.ADMIN_IDS:
        try:
            await bot.send_message(chat_id=manager_id, text=order_text, parse_mode="HTML")
            sent_count += 1
        except Exception as error:
            logger.exception("Failed to send product request to manager '%s': %s", manager_id, error)

    if sent_count == 0:
        await callback.answer(locale.buy_request_error(), show_alert=True)
        return

    await callback.answer(locale.buy_request_sent(), show_alert=True)
    await callback.message.answer(
        locale.buy_request_sent(),
        reply_markup=await get_manager_chat_keyboard(locale)
    )
