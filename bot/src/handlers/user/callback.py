from aiogram import Router, Bot, F
from aiogram.types import CallbackQuery
from fluentogram import TranslatorRunner
from aiogram.utils.keyboard import InlineKeyboardBuilder
from src.utils.db import Database
from src.handlers.user.keyboards import get_start_kb
from src.utils.db import db
from src.utils.filters import IsAdmin

from .keyboards import get_assortment_keyboard, get_models_keyboard


router = Router()


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
    category = callback.data.replace("cat_", "").strip()

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
    model_name = callback.data.replace("model_", "").strip()

    product = await db.get_product_details(model_name)

    if not product:
        await callback.answer("Товар временно отсутствует 😔", show_alert=True)
        return

    text = (
        f"📱 <b>{product.get('model', 'Без названия')}</b>\n\n"
        f"💰 <b>{product.get('price', 'Цена отсутствует')}</b>\n\n"
        f"{product.get('description', 'Описание отсутствует')}\n\n"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="🛒 Купить",
              url="https://t.me/allvade")
    kb.button(text="⬅️ Назад к моделям",
              callback_data=f"del_card_with_exit")
    kb.adjust(1)

    try:
        if product.get("photo_id"):

            await callback.message.answer_photo(
                photo=product["photo_id"],
                caption=text,
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                text=text,
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
    except Exception as e:
        print(f"Ошибка при отправке карточки: {e}")
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
