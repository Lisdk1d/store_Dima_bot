from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup


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
