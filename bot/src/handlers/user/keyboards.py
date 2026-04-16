from fluentogram import TranslatorRunner
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_start_kb(locale) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=locale.asort_button(), callback_data="asort")
    builder.button(text=locale.cart_button(), callback_data="cart_show")
    builder.button(text=locale.manager_button(), url="https://t.me/allvade")
    builder.button(text=locale.locale_button(), callback_data="address")
    builder.button(text=locale.trans_button(), callback_data="delivery")
    builder.button(text=locale.reviews_button(), callback_data="reviews")
    builder.button(text=locale.site_button(), url="https://storedima.ru")
    builder.adjust(1, 1, 1, 2, 2)
    return builder.as_markup()


async def get_assortment_keyboard(categories: list, locale: TranslatorRunner) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in categories:
        category_text = str(category).strip()
        if not category_text:
            continue
        builder.button(text=category_text, callback_data=f"cat_{category_text}")

    builder.adjust(1)
    builder.row(InlineKeyboardButton(
        text=locale.main_menu_button(), callback_data="main_menu"))
    return builder.as_markup()


async def get_models_keyboard(category: str, models: list, locale: TranslatorRunner) -> InlineKeyboardMarkup:
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
        text=locale.to_categories_button(),
        callback_data="del_card_with_exit"
    ))

    return builder.as_markup()


async def get_item_actions_keyboard(model_name: str, price: int | str, locale: TranslatorRunner) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    # Keep callback payload compact and stable; price is resolved from DB on click.
    cart_callback_data = f"add_to_cart|{model_name}"
    buy_callback_data = f"buy_product|{model_name}"

    builder.row(
        InlineKeyboardButton(text=locale.buy_button(), callback_data=buy_callback_data),
        InlineKeyboardButton(text=locale.add_to_cart_button(), callback_data=cart_callback_data)
    )

    builder.row(
        InlineKeyboardButton(text=locale.back_button(),
                             callback_data="del_card_with_exit")
    )

    return builder.as_markup()


async def get_cart_actions_keyboard(cart_items: list[dict], locale: TranslatorRunner) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    remove_buttons = [
        InlineKeyboardButton(
            text=locale.cart_remove_button(index=index + 1),
            callback_data=f"cart_remove|{index}"
        )
        for index, _ in enumerate(cart_items)
    ]

    for i in range(0, len(remove_buttons), 2):
        builder.row(*remove_buttons[i:i + 2])

    builder.row(
        InlineKeyboardButton(text=locale.cart_clear_button(), callback_data="cart_clear")
    )
    # Explicitly place these two buttons in one row.
    builder.row(
        InlineKeyboardButton(text=locale.buy_button(), callback_data="cart_checkout"),
        InlineKeyboardButton(text=locale.cart_back_button(), callback_data="main_menu")
    )
    return builder.as_markup()


async def get_cart_empty_keyboard(locale: TranslatorRunner) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=locale.cart_back_button(), callback_data="main_menu")
    )
    return builder.as_markup()


async def get_info_back_keyboard(locale: TranslatorRunner) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=locale.cart_back_button(), callback_data="del_card_with_exit")
    )
    return builder.as_markup()


async def get_manager_chat_keyboard(locale: TranslatorRunner) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=locale.manager_chat_button(), url="https://t.me/allvade")
    )
    return builder.as_markup()
