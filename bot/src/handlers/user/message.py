from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import Message
from fluentogram import TranslatorRunner
from .keyboards import get_start_kb
from aiogram.fsm.context import FSMContext
from src.utils.states import ProductForm
from src.utils.filters import IsAdmin
from src.utils.db import db

router = Router()


@router.message(Command("start"))
async def Start_Message(message: Message,
                        bot: Bot,
                        locale: TranslatorRunner):
    await message.answer(
        text=locale.welcome_text(name=message.from_user.first_name),
        reply_markup=get_start_kb(locale)
    )


@router.message(F.text == "/add")
async def start_add(message: Message, state: FSMContext):
    await message.answer("Введите описание товара:")
    await state.set_state(ProductForm.waiting_for_description)


@router.message(ProductForm.waiting_for_description)
async def get_description(message: Message, state: FSMContext):
    await state.update_data(desc=message.text)
    await message.answer("Теперь отправьте фото:")
    await state.set_state(ProductForm.waiting_for_photo)


@router.message(ProductForm.waiting_for_photo, F.photo)
async def get_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    description = data['desc']
    photo_id = message.photo[-1].file_id

    # ВЫЗОВ ТВОЕГО МЕТОДА ИЗ КЛАССА DATABASE
    try:
        inserted_id = await db.add_product(description, photo_id, message.from_user.id)
        await message.answer(f"✅ Товар сохранен в MongoDB!\nID: {inserted_id}")
    except Exception as e:
        await message.answer(f"❌ Ошибка при записи в базу: {e}")

    await state.clear()
