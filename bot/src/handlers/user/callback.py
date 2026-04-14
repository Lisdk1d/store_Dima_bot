import logging

from aiogram import Router, Bot, F
from aiogram.types import CallbackQuery
from fluentogram import TranslatorRunner
from src.handlers.user.keyboards import get_start_kb, get_item_actions_keyboard, get_cart_actions_keyboard
from src.utils.db import db
from .cart_utils import build_cart_text


from .keyboards import get_assortment_keyboard, get_models_keyboard


router = Router()
logger = logging.getLogger(__name__)

def _parse_add_to_cart_callback(callback_data: str) -> tuple[str, int] | None:
    """Parse callback payload format: add_to_cart|<model_name>|<price>."""
    parts = callback_data.split("|", maxsplit=2)
    if len(parts) != 3:
        return None

    model_name = parts[1].strip()
    if not model_name:
        return None

    try:
        price = int(parts[2])
    except (TypeError, ValueError):
        return None

    return model_name, price


@router.callback_query(lambda c: c.data == "reviews")
async def show_reviews(callback: CallbackQuery,
                       bot: Bot,
                       locale: TranslatorRunner):
    await callback.message.answer(locale.reviews_callback())


@router.callback_query(lambda c: c.data == "address")
async def show_adrdress(callback: CallbackQuery,
                        bot: Bot,
                        locale: TranslatorRunner):
    await callback.message.answer(locale.locale_callback())


@router.callback_query(lambda c: c.data == "delivery")
async def show_delivery(callback: CallbackQuery,
                        bot: Bot,
                        locale: TranslatorRunner):
    await callback.message.answer(locale.trans_callback())


@router.callback_query(F.data == "asort")
async def show_categories(callback: CallbackQuery,
                          locale: TranslatorRunner):
    categories = await db.get_unique_categories()

    if not categories:
        await callback.message.edit_text("Пока нет товаров в наличии 😔")
        return

    await callback.message.edit_text(
        text="Выберите категорию техники:",
        reply_markup=await get_assortment_keyboard(categories)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat_"))
async def show_models(callback: CallbackQuery):
    callback_data = callback.data or ""
    category = callback_data.replace("cat_", "").strip()

    models = await db.get_models_by_category(category)

    if not models:
        await callback.message.answer("Пока нет товаров в наличии 😔")
        await callback.answer()
        return

    await callback.message.answer(
        text=f"📁 Категория: <b>{category}</b>\n\nВыберите модель:",
        reply_markup=await get_models_keyboard(category, models)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("model_"))
async def show_product_card(callback: CallbackQuery):
    callback_data = callback.data or ""
    model_name = callback_data.replace("model_", "").strip()

    product = await db.get_product_details(model_name)

    if not product:
        await callback.answer("Товар временно отсутствует 😔", show_alert=True)
        return

    text = (
        f"📱 <b>{product.get('model', 'Без названия')}</b>\n\n"
        f"💰 <b>{product.get('price', 'Цена отсутствует')}</b>\n\n"
        f"{product.get('description', 'Описание отсутствует')}\n\n"
    )

    try:
        if product.get("photo_id"):
            await callback.message.answer_photo(
                photo=product["photo_id"],
                caption=text,
                reply_markup=await get_item_actions_keyboard(
                    model_name=product.get("model", ""),
                    price=product.get("price", 0)
                ),
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                text=text,
                reply_markup=await get_item_actions_keyboard(
                    model_name=product.get("model", ""),
                    price=product.get("price", 0)
                ),
                parse_mode="HTML"
            )
    except Exception as error:
        logger.exception("Ошибка при отправке карточки товара '%s': %s", model_name, error)
        await callback.answer("Ошибка при отображении товара", show_alert=True)

    await callback.answer()


@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery, locale: TranslatorRunner):
    await callback.message.edit_text(
        text=locale.welcome_text(name=callback.from_user.first_name),
        reply_markup=get_start_kb(locale)
    )


@router.callback_query(F.data == "del_card_with_exit")
async def back_to_models_list(callback: CallbackQuery,
                              locale: TranslatorRunner):
    await callback.message.delete()


@router.callback_query(F.data.startswith("add_to_cart|"))
async def add_item_to_cart(callback: CallbackQuery):
    if callback.from_user is None:
        await callback.answer("Пользователь не определён", show_alert=True)
        return

    callback_data = callback.data or ""
    parsed_data = _parse_add_to_cart_callback(callback_data)
    if not parsed_data:
        await callback.answer("Не удалось добавить товар в корзину", show_alert=True)
        return

    model_name, price = parsed_data
    await db.add_to_cart(
        user_id=callback.from_user.id,
        model_name=model_name,
        price=price
    )
    await callback.answer("Товар добавлен в корзину ✅")


@router.callback_query(F.data == "cart_show")
async def show_cart_from_menu(callback: CallbackQuery):
    if callback.from_user is None:
        await callback.answer("Пользователь не определён", show_alert=True)
        return

    cart_items = await db.get_cart(callback.from_user.id)
    cart_text = build_cart_text(cart_items)
    if cart_items:
        await callback.message.edit_text(
            cart_text,
            parse_mode="HTML",
            reply_markup=await get_cart_actions_keyboard(cart_items)
        )
    else:
        await callback.message.edit_text(cart_text, parse_mode="HTML")

    await callback.answer()


@router.callback_query(F.data == "cart_clear")
async def clear_cart(callback: CallbackQuery):
    if callback.from_user is None:
        await callback.answer("Пользователь не определён", show_alert=True)
        return

    await db.clear_cart(callback.from_user.id)
    await callback.message.edit_text("🛒 <b>Ваша корзина пуста</b>", parse_mode="HTML")
    await callback.answer("Корзина очищена")


@router.callback_query(F.data.startswith("cart_remove|"))
async def remove_cart_item(callback: CallbackQuery):
    if callback.from_user is None:
        await callback.answer("Пользователь не определён", show_alert=True)
        return

    callback_data = callback.data or ""
    try:
        _, raw_index = callback_data.split("|", maxsplit=1)
        item_index = int(raw_index)
    except (ValueError, TypeError):
        await callback.answer("Неверный индекс позиции", show_alert=True)
        return

    removed = await db.remove_item_from_cart(callback.from_user.id, item_index)
    if not removed:
        await callback.answer("Не удалось удалить позицию", show_alert=True)
        return

    updated_cart = await db.get_cart(callback.from_user.id)
    cart_text = build_cart_text(updated_cart)
    if updated_cart:
        await callback.message.edit_text(
            cart_text,
            parse_mode="HTML",
            reply_markup=await get_cart_actions_keyboard(updated_cart)
        )
    else:
        await callback.message.edit_text(cart_text, parse_mode="HTML")

    await callback.answer("Позиция удалена")
