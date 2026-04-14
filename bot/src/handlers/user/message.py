import logging
import re

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from fluentogram import TranslatorRunner

from src.utils.states import ProductForm, DeleteProcess
from src.utils.filters import IsAdmin
from src.utils.db import db
from .keyboards import (
    get_start_kb,
    get_models_keyboard,
    get_assortment_keyboard,
    get_cart_actions_keyboard,
    get_cart_empty_keyboard,
)
from .cart_utils import build_cart_text

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("start"))
async def start_message(message: Message, locale: TranslatorRunner):
    await db.create_user(
        user_id=message.from_user.id,
        username=message.from_user.username
    )

    await message.answer(
        text=locale.welcome_text(name=message.from_user.full_name),
        reply_markup=get_start_kb(locale)
    )


@router.message(Command("cart"), StateFilter("*"))
async def show_cart(message: Message, locale: TranslatorRunner):
    cart_items = await db.get_cart(message.from_user.id)
    text = build_cart_text(cart_items, locale)

    if cart_items:
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=await get_cart_actions_keyboard(cart_items, locale)
        )
        return

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=await get_cart_empty_keyboard(locale)
    )


@router.message(Command("add"), IsAdmin())
async def cmd_add(message: Message, state: FSMContext, locale: TranslatorRunner):
    categories = await db.get_all_categories()
    if categories:
        categories_text = "\n".join(f"    {category}" for category in categories)
    else:
        categories_text = locale.add_product_no_categories()

    await message.answer(
        locale.add_product_start(categories_list=categories_text),
        parse_mode="HTML"
    )
    await state.set_state(ProductForm.waiting_for_category)


@router.message(ProductForm.waiting_for_category, IsAdmin())
async def process_category(message: Message, state: FSMContext, locale: TranslatorRunner):
    category_text = (message.text or "").strip()
    if not category_text:
        await message.answer(locale.category_empty_error())
        return

    await state.update_data(category=category_text)
    await message.answer(locale.category_saved_next())
    await state.set_state(ProductForm.waiting_for_model)


@router.message(ProductForm.waiting_for_model, IsAdmin())
async def process_model(message: Message, state: FSMContext, locale: TranslatorRunner):
    model_text = (message.text or "").strip()
    if not model_text:
        await message.answer(locale.model_empty_error())
        return

    await state.update_data(model=model_text)
    await message.answer(locale.model_saved_next())
    await state.set_state(ProductForm.waiting_for_description)


@router.message(ProductForm.waiting_for_description, IsAdmin())
async def process_description(message: Message, state: FSMContext, locale: TranslatorRunner):
    description_text = (message.text or "").strip()
    if not description_text:
        await message.answer(locale.description_empty_error())
        return

    await state.update_data(description=description_text)
    await message.answer(locale.description_saved_next())
    await state.set_state(ProductForm.waiting_for_price)


@router.message(ProductForm.waiting_for_price, IsAdmin())
async def process_price(message: Message, state: FSMContext, locale: TranslatorRunner):
    price_text = (message.text or "").strip()
    if not price_text:
        await message.answer(locale.price_empty_error())
        return

    # Accept formats like "120000", "120 000", "120,000".
    normalized_price = re.sub(r"[^\d]", "", price_text)
    if not normalized_price:
        await message.answer(locale.price_invalid_error())
        return

    await state.update_data(price=int(normalized_price))
    await message.answer(locale.price_saved_next())
    await state.set_state(ProductForm.waiting_for_photo)


@router.message(ProductForm.waiting_for_photo, F.photo, IsAdmin())
async def process_photo(message: Message, state: FSMContext, locale: TranslatorRunner):
    data = await state.get_data()

    try:
        inserted_id = await db.add_product(
            category=data["category"],
            model=data["model"],
            description=data["description"],
            price=data["price"],
            photo_id=message.photo[-1].file_id,
            stock=1
        )

        await message.answer(
            locale.product_added_success(
                id=inserted_id,
                category=data["category"],
                model=data["model"],
                price=data["price"]
            )
        )
    except Exception as error:
        logger.exception("Ошибка при добавлении товара администратором: %s", error)
        await message.answer(locale.product_added_error())

    await state.clear()


@router.message(Command("del_from_db"), IsAdmin())
async def start_delete(message: Message, state: FSMContext, locale: TranslatorRunner):
    await message.answer(locale.delete_product_start(), parse_mode="HTML")
    await state.set_state(DeleteProcess.waiting_for_del_model)


@router.message(DeleteProcess.waiting_for_del_model, IsAdmin())
async def delete_process(message: Message, state: FSMContext, locale: TranslatorRunner):
    model_name = (message.text or "").strip()
    if not model_name:
        await message.answer(locale.delete_model_empty_error())
        return

    try:
        result = await db.products.delete_one({"model": model_name})
    except Exception as error:
        logger.exception("Ошибка при удалении модели '%s': %s", model_name, error)
        await message.answer(locale.delete_model_error())
        return

    if result.deleted_count > 0:
        await message.answer(locale.delete_success(model_name=model_name))
    else:
        await message.answer(locale.delete_not_found(model_name=model_name))


