import logging

from aiogram import Router, Bot, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from fluentogram import TranslatorRunner
from src.handlers.user.keyboards import (
    get_start_kb,
    get_item_actions_keyboard,
    get_cart_actions_keyboard,
    get_cart_empty_keyboard,
    get_info_back_keyboard,
)
from src.utils.db import db
from src.utils.states import CheckoutProcess
from src.handlers.user.cart_utils import (
    build_cart_text,
    format_price_with_ruble,
)


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


def _parse_buy_product_callback(callback_data: str) -> str | int | None:
    if not callback_data.startswith("buy_product|"):
        return None
    payload = callback_data[len("buy_product|"):].strip()
    if not payload:
        return None
    if payload.isdigit():
        return int(payload)
    return payload


async def _resolve_product(identifier: str | int) -> dict | None:
    if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
        return await db.get_product_by_id(int(identifier))
    return await db.get_product_details(str(identifier))


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
        f"💰 <b>{format_price_with_ruble(product.get('price', locale.unknown_product_price()))}</b>\n\n"
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
                    locale=locale,
                    product_id=product.get("id"),
                ),
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                text=text,
                reply_markup=await get_item_actions_keyboard(
                    model_name=product.get("model", ""),
                    price=product.get("price", 0),
                    locale=locale,
                    product_id=product.get("id"),
                ),
                parse_mode="HTML"
            )
    except Exception as error:
        logger.exception("Ошибка при отправке карточки товара '%s': %s", model_name, error)
        await callback.answer(locale.product_display_error(), show_alert=True)

    await callback.answer()


@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery, locale: TranslatorRunner):
    text = locale.welcome_text(name=callback.from_user.full_name)
    markup = get_start_kb(locale)
    try:
        await callback.message.edit_text(text=text, reply_markup=markup)
    except Exception:
        await callback.message.answer(text=text, reply_markup=markup)
    await callback.answer()


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

    price = format_price_with_ruble(product.get("price", ""))
    if not price:
        await callback.answer(locale.invalid_product_price(), show_alert=True)
        return

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
async def checkout_cart(callback: CallbackQuery, state: FSMContext, locale: TranslatorRunner):
    if callback.from_user is None:
        await callback.answer(locale.user_not_defined(), show_alert=True)
        return

    cart_items = await db.get_cart(callback.from_user.id)
    if not cart_items:
        await callback.answer(locale.cart_empty(), show_alert=True)
        return

    await state.set_state(CheckoutProcess.waiting_for_address)
    await state.update_data(checkout_type="cart")
    await callback.message.edit_text(locale.delivery_enter_address(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("buy_product|"))
async def checkout_product_from_card(callback: CallbackQuery, state: FSMContext, locale: TranslatorRunner):
    if callback.from_user is None:
        await callback.answer(locale.user_not_defined(), show_alert=True)
        return

    callback_data = callback.data or ""
    identifier = _parse_buy_product_callback(callback_data)
    if identifier is None:
        await callback.answer(locale.buy_request_error(), show_alert=True)
        return

    product = await _resolve_product(identifier)
    if not product:
        await callback.answer(locale.cart_product_not_found(), show_alert=True)
        return

    product_id = product.get("id")
    await state.set_state(CheckoutProcess.waiting_for_quantity)
    await state.update_data(checkout_type="single", product_id=product_id)
    await callback.message.answer(
        locale.quantity_enter(model=product.get("model", "")),
        parse_mode="HTML",
    )
    await callback.answer()
