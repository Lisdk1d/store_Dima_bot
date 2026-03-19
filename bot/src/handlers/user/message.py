from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message
from fluentogram import TranslatorRunner

router = Router()


@router.message(Command("start"))
async def Start_Message(message: Message,
                        bot: Bot,
                        locale: TranslatorRunner):
    await message.answer(locale.welcome_text())
