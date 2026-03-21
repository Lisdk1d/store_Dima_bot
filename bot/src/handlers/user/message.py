from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message
from fluentogram import TranslatorRunner
from .keyboards import get_start_kb

router = Router()


@router.message(Command("start"))
async def Start_Message(message: Message,
                        bot: Bot,
                        locale: TranslatorRunner):
    await message.answer(
        text=locale.welcome_text(name=message.from_user.first_name),
        reply_markup=get_start_kb(locale)
    )
