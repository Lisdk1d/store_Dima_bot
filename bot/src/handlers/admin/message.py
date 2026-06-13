import logging

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from fluentogram import TranslatorRunner

from src.utils.states import EditProductForm, DeleteCategoryProcess
from src.utils.filters import IsAdmin
from src.utils.db import db
from src.handlers.user.cart_utils import format_price_with_ruble
from .keyboards import get_edit_field_keyboard

router = Router()
logger = logging.getLogger(__name__)

EDITABLE_FIELDS = {
    "category": "category",
    "model": "model",
    "description": "description",
    "price": "price",
    "photo": "photo",
    "stock": "stock",
}


@router.message(Command("edit"), IsAdmin())
async def cmd_edit(message: Message, state: FSMContext, locale: TranslatorRunner):
    await message.answer(locale.edit_product_start(), parse_mode="HTML")
    await state.set_state(EditProductForm.waiting_for_model)


@router.message(EditProductForm.waiting_for_model, IsAdmin())
async def edit_select_model(message: Message, state: FSMContext, locale: TranslatorRunner):
    model_name = (message.text or "").strip()
    if not model_name:
        await message.answer(locale.edit_model_empty_error())
        return

    product = await db.get_product_by_model(model_name)
    if not product:
        await message.answer(locale.edit_not_found(model_name=model_name))
        return

    await state.update_data(original_model=model_name, product=product)
    await message.answer(
        locale.edit_choose_field(
            category=product["category"],
            model=product["model"],
            price=format_price_with_ruble(product["price"]),
            stock=product["stock"],
        ),
        parse_mode="HTML",
        reply_markup=get_edit_field_keyboard(locale),
    )
    await state.set_state(EditProductForm.waiting_for_field)


@router.callback_query(F.data.startswith("edit_field|"), EditProductForm.waiting_for_field, IsAdmin())
async def edit_choose_field(callback: CallbackQuery, state: FSMContext, locale: TranslatorRunner):
    field = (callback.data or "").replace("edit_field|", "").strip()
    if field not in EDITABLE_FIELDS:
        await callback.answer(locale.edit_field_invalid(), show_alert=True)
        return

    await state.update_data(edit_field=field)
    data = await state.get_data()
    product = data.get("product", {})

    if field == "photo":
        await callback.message.answer(locale.edit_send_photo())
        await state.set_state(EditProductForm.waiting_for_new_photo)
    else:
        current_value = product.get(field, "")
        await callback.message.answer(
            locale.edit_enter_new_value(field=field, current_value=current_value),
            parse_mode="HTML",
        )
        await state.set_state(EditProductForm.waiting_for_new_value)

    await callback.answer()


@router.message(EditProductForm.waiting_for_new_value, IsAdmin())
async def edit_apply_value(message: Message, state: FSMContext, locale: TranslatorRunner):
    data = await state.get_data()
    original_model = data.get("original_model")
    field = data.get("edit_field")
    new_value = (message.text or "").strip()

    if not new_value:
        await message.answer(locale.edit_value_empty_error())
        return

    if field == "stock":
        try:
            new_value = int(new_value)
        except ValueError:
            await message.answer(locale.edit_stock_invalid())
            return

    update_kwargs = {field: new_value}
    success = await db.update_product(original_model, **update_kwargs)

    if success:
        if field == "model":
            await state.update_data(original_model=new_value)
        await message.answer(
            locale.edit_success(field=field, value=new_value),
            parse_mode="HTML",
        )
    else:
        await message.answer(locale.edit_failed())

    await state.clear()


@router.message(EditProductForm.waiting_for_new_photo, F.photo, IsAdmin())
async def edit_apply_photo(message: Message, state: FSMContext, locale: TranslatorRunner):
    data = await state.get_data()
    original_model = data.get("original_model")
    photo_id = message.photo[-1].file_id

    success = await db.update_product(original_model, photo_id=photo_id)
    if success:
        await message.answer(locale.edit_photo_success())
    else:
        await message.answer(locale.edit_failed())

    await state.clear()


@router.message(Command("del_category"), IsAdmin())
async def cmd_del_category(message: Message, state: FSMContext, locale: TranslatorRunner):
    categories = await db.get_all_categories()
    if categories:
        categories_text = "\n".join(f"    {category}" for category in categories)
    else:
        categories_text = locale.add_product_no_categories()

    await message.answer(
        locale.delete_category_start(categories_list=categories_text),
        parse_mode="HTML",
    )
    await state.set_state(DeleteCategoryProcess.waiting_for_category)


@router.message(DeleteCategoryProcess.waiting_for_category, IsAdmin())
async def delete_category_process(message: Message, state: FSMContext, locale: TranslatorRunner):
    category_name = (message.text or "").strip()
    if not category_name:
        await message.answer(locale.category_empty_error())
        return

    deleted_count = await db.delete_category(category_name)
    if deleted_count > 0:
        await message.answer(
            locale.delete_category_success(category=category_name, count=deleted_count),
            parse_mode="HTML",
        )
    else:
        await message.answer(locale.delete_category_not_found(category=category_name))

    await state.clear()
