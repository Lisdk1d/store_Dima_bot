import logging
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat

from fluentogram import TranslatorHub, FluentTranslator
from fluent_compiler.bundle import FluentBundle

from src.utils.config import settings
from src.utils.middlewares import ThrottlingMiddleware, TranslateMiddleware, AlbumMiddleware
from src.handlers import router as main_router
from src.utils.db import db


logging.basicConfig(lavel=logging.INFO)
logger = logging.getLogger(__name__)


t_hub = TranslatorHub(
    {
        "ru": ("ru",)
    },
    translators=[
        FluentTranslator(
            "ru",
            translator=FluentBundle.from_files(
                "ru-RU",
                filenames=[
                    "src/i18n/ru/text.ftl",
                    "src/i18n/ru/button.ftl",
                ]
            ),
        )
    ],
    root_locale="ru",
)


async def on_startup(bot: Bot):
    await setup_commands(bot)
    await db.check_connection()


async def setup_commands(bot: Bot):
    user_commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="cart", description="Открыть корзину"),
    ]
    admin_commands = user_commands + [
        BotCommand(command="add", description="Добавить товар"),
        BotCommand(command="del_from_db", description="Удалить товар"),
    ]

    await bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())
    for admin_id in settings.ADMIN_IDS:
        await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))


async def main():
    session = AiohttpSession()
    bot = Bot(
        token=settings.BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode="HTML")
    )

    dp = Dispatcher(t_hub=t_hub)
    dp.message.middleware(ThrottlingMiddleware())
#    dp.message.outer_middleware(UserMiddleware())
    dp.message.outer_middleware(TranslateMiddleware())
    dp.message.outer_middleware(AlbumMiddleware())

    dp.callback_query.middleware(ThrottlingMiddleware())
#    dp.callback_query.outer_middleware(UserMiddleware())
    dp.callback_query.outer_middleware(TranslateMiddleware())
    dp.callback_query.outer_middleware(AlbumMiddleware())

    dp.include_router(main_router)

    try:
        dp.startup.register(on_startup)
        await dp.start_polling(bot)
    except ValueError as e:
        logger.error("ValueError occurred: %s: ", e)
    except KeyError as e:
        logger.error("KeyError occurred: %s", e)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
