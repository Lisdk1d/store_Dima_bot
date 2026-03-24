from aiogram import Router, Bot, F
from aiogram.types import CallbackQuery, InputMediaPhoto
from fluentogram import TranslatorRunner

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
async def show_categories(callback: CallbackQuery):
    await callback.message.edit_text(
        text="Выберите категорию техники:",
        reply_markup=get_assortment_keyboard()
    )


@router.callback_query(F.data.startswith("cat_"))
async def show_models(callback: CallbackQuery):
    category = callback.data.split("_")[1]
    await callback.message.edit_text(
        f"Модели в категории {category}:",
        reply_markup=get_models_keyboard(category)
    )


@router.callback_query(F.data == "back_to_assortment")
async def back_to_assortment(callback: CallbackQuery):
    await show_categories(callback)
