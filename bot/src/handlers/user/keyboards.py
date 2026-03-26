from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_start_kb(locale) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=locale.asort_button(), callback_data="asort")
    builder.button(text=locale.manager_button(), url="https://t.me/allvade")
    builder.button(text=locale.locale_button(), callback_data="address")
    builder.button(text=locale.trans_button(), callback_data="delivery")
    builder.button(text=locale.reviews_button(), callback_data="reviews")
    builder.button(text=locale.site_button(), url="https://storedima.ru")
    builder.adjust(1, 1, 2, 2)
    return builder.as_markup()


async def get_assortment_keyboard(categories: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in categories:
        builder.button(text=str(cat), callback_data=f"cat_{cat}")

    builder.adjust(1)
    builder.row(InlineKeyboardButton(
        text="⬅️ Главное меню", callback_data="main_menu"))
    return builder.as_markup()


async def get_models_keyboard(category: str, models: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for model in models:
        model_str = str(model).strip()
        if model_str:

            button_text = model_str if len(
                model_str) > 2 else model_str.upper()
            builder.button(
                text=button_text,
                callback_data=f"model_{model_str}"
            )

    builder.adjust(1 if len(models) <= 2 else 2)

    builder.row(InlineKeyboardButton(
        text=f"⬅️ К категориям",
        callback_data="del_card_with_exit"
    ))

    return builder.as_markup()
