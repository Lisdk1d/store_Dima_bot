from fluentogram import TranslatorRunner
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_edit_field_keyboard(locale: TranslatorRunner) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    fields = [
        ("category", locale.edit_field_category()),
        ("model", locale.edit_field_model()),
        ("description", locale.edit_field_description()),
        ("price", locale.edit_field_price()),
        ("photo", locale.edit_field_photo()),
        ("stock", locale.edit_field_stock()),
    ]
    for field_key, label in fields:
        builder.button(text=label, callback_data=f"edit_field|{field_key}")
    builder.adjust(2)
    return builder.as_markup()


def get_payment_methods_keyboard(
    locale: TranslatorRunner,
    prefix: str = "pay",
    back_callback: str = "main_menu",
) -> InlineKeyboardMarkup:
    """Payment method selection with configurable back button."""
    builder = InlineKeyboardBuilder()
    methods = [
        ("card", locale.payment_method_card()),
        ("sbp", locale.payment_method_sbp()),
        ("cash", locale.payment_method_cash()),
    ]
    for method_key, label in methods:
        builder.button(text=label, callback_data=f"{prefix}|{method_key}")
    builder.adjust(1)
    builder.row(
        InlineKeyboardButton(text=locale.cart_back_button(), callback_data=back_callback)
    )
    return builder.as_markup()
