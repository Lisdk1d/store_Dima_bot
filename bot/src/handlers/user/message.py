from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext

from fluentogram import TranslatorRunner

from src.utils.states import ProductForm, DeleteProcess
from src.utils.filters import IsAdmin
from src.utils.db import db
from .keyboards import get_start_kb, get_models_keyboard, get_assortment_keyboard

router = Router()


@router.message(Command("start"))
async def start_message(message: Message, locale: TranslatorRunner):
    await message.answer(
        text=locale.welcome_text(name=message.from_user.first_name),
        reply_markup=get_start_kb(locale)
    )


@router.message(Command("add"), IsAdmin())
async def cmd_add(message: Message, state: FSMContext):
    await message.answer("Введите **категорию** товара (например: Смартфоны, Ноутбуки и т.д.):")
    await state.set_state(ProductForm.waiting_for_category)


@router.message(ProductForm.waiting_for_category, IsAdmin())
async def process_category(message: Message, state: FSMContext):
    await state.update_data(category=message.text.strip())
    await message.answer("Введите **модель** товара:")
    await state.set_state(ProductForm.waiting_for_model)


@router.message(ProductForm.waiting_for_model, IsAdmin())
async def process_model(message: Message, state: FSMContext):
    await state.update_data(model=message.text.strip())
    await message.answer("Введите **описание** товара:")
    await state.set_state(ProductForm.waiting_for_description)


@router.message(ProductForm.waiting_for_description, IsAdmin())
async def process_model(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await message.answer("Введите **стоимость** товара:")
    await state.set_state(ProductForm.waiting_for_price)


@router.message(ProductForm.waiting_for_price, IsAdmin())
async def process_description(message: Message, state: FSMContext):
    await state.update_data(price=message.text)
    await message.answer("Теперь отправьте **одно фото** товара:")
    await state.set_state(ProductForm.waiting_for_photo)


@router.message(ProductForm.waiting_for_photo, F.photo, IsAdmin())
async def process_photo(message: Message, state: FSMContext):
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
            f"✅ Товар успешно добавлен в базу!\n\n"
            f"🆔 ID: <code>{inserted_id}</code>\n"
            f"📁 Категория: {data['category']}\n"
            f"📱 Модель: {data['model']}\n"
            f"💰 Цена: {data['price']}"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка при добавлении товара:\n{str(e)}")

    await state.clear()


@router.message(Command("del_from_db"), IsAdmin())
async def start_delete(message: Message, state: FSMContext):
    await message.answer("Введите название модели, которую нужно удалить из базы >>>")
    await state.set_state(DeleteProcess.waiting_for_del_model)


@router.message(DeleteProcess.waiting_for_del_model, IsAdmin())
async def delete_process(message: Message, state: FSMContext):
    model_name = message.text

    result = await db.products.delete_one({"model": model_name})

    if result.deleted_count > 0:
        await message.answer(f"Документ с моделью {model_name} успешно удалён из базы")
    else:
        await message.answer(f"Модель {model_name} не найдена в базе. Проверьте правильность написания")
