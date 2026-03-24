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


def get_assortment_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    categories = ["Смартфоны", "Планшеты", "Ноутбуки"]
    for cat in categories:
        builder.row(InlineKeyboardButton(text=cat, callback_data=f"cat_{cat}"))
    builder.row(InlineKeyboardButton(
        text="⬅️ Назад", callback_data="main_menu"))
    return builder.as_markup()


def get_models_keyboard(category: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if category == "Смартфоны":
        models = ["15", "16", "17", "17 Pro", "17 Pro Max"]
        for model in models:
            builder.row(InlineKeyboardButton(
                text=model, callback_data=f"model_{model}"))

    builder.row(InlineKeyboardButton(text="⬅️ К категориям",
                callback_data="back_to_assortment"))
    return builder.as_markup()
