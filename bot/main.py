import logging
import asyncio
import sys

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.exceptions import TelegramUnauthorizedError

from fluentogram import TranslatorHub, FluentTranslator
from fluent_compiler.bundle import FluentBundle

from src.utils.config import settings
from src.utils.middlewares import ThrottlingMiddleware, TranslateMiddleware, AlbumMiddleware
from src.handlers import router as main_router
from src.utils.db import db


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_PLACEHOLDER_TOKENS = {
    "",
    "your_telegram_bot_token",
    "0000000000:TEST_TOKEN_PLACEHOLDER",
}


def _token_looks_invalid(token: str) -> bool:
    token = (token or "").strip()
    if token in _PLACEHOLDER_TOKENS:
        return True
    # Telegram bot tokens: <bot_id>:<secret>
    if ":" not in token:
        return True
    bot_id, secret = token.split(":", maxsplit=1)
    return not bot_id.isdigit() or not secret


t_hub = TranslatorHub(
    {"ru": ("ru",)},
    translators=[
        FluentTranslator(
            "ru",
            translator=FluentBundle.from_files(
                "ru-RU",
                filenames=[
                    "src/i18n/ru/text.ftl",
                    "src/i18n/ru/button.ftl",
                ],
            ),
        )
    ],
    root_locale="ru",
)


async def validate_bot_token(bot: Bot) -> None:
    """Verify token with Telegram before starting polling/webhook."""
    if _token_looks_invalid(settings.BOT_TOKEN):
        logger.error(
            "BOT_TOKEN is missing or still a placeholder. "
            "Get a token from @BotFather and set it in .env:\n"
            "  BOT_TOKEN=123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        )
        sys.exit(1)

    try:
        me = await bot.get_me()
        logger.info("Bot authorized: @%s (id=%s)", me.username, me.id)
    except TelegramUnauthorizedError:
        logger.error(
            "BOT_TOKEN is invalid (Telegram returned Unauthorized). "
            "Check the token in .env — no quotes, no spaces, copy the full string from @BotFather."
        )
        sys.exit(1)
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
        BotCommand(command="edit", description="Редактировать товар"),
        BotCommand(command="del_from_db", description="Удалить товар"),
        BotCommand(command="del_category", description="Удалить категорию"),
    ]

    try:
        await bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())
        for admin_id in settings.ADMIN_IDS:
            await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
    except Exception as error:
        logger.warning("Could not register bot commands: %s", error)


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher(t_hub=t_hub)
    dp.message.middleware(ThrottlingMiddleware())
    dp.message.outer_middleware(TranslateMiddleware())
    dp.message.outer_middleware(AlbumMiddleware())
    dp.callback_query.middleware(ThrottlingMiddleware())
    dp.callback_query.outer_middleware(TranslateMiddleware())
    dp.callback_query.outer_middleware(AlbumMiddleware())
    dp.include_router(main_router)
    dp.startup.register(on_startup)
    return dp


async def run_polling():
    session = AiohttpSession()
    bot = Bot(
        token=settings.BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dp = create_dispatcher()
    try:
        await validate_bot_token(bot)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


async def run_webhook():
    session = AiohttpSession()
    bot = Bot(
        token=settings.BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    await validate_bot_token(bot)
    dp = create_dispatcher()

    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=settings.WEBHOOK_SECRET or None,
    )
    webhook_requests_handler.register(app, path=settings.WEBHOOK_PATH)

    setup_application(app, dp, bot=bot)

    async def on_app_startup(_app):
        await bot.set_webhook(
            url=settings.webhook_url,
            secret_token=settings.WEBHOOK_SECRET or None,
            drop_pending_updates=True,
        )
        logger.info("Webhook set to %s", settings.webhook_url)

    async def on_app_shutdown(_app):
        await bot.delete_webhook()
        await bot.session.close()

    app.on_startup.append(on_app_startup)
    app.on_shutdown.append(on_app_shutdown)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.WEBAPP_HOST, settings.WEBAPP_PORT)
    logger.info("Starting webhook server on %s:%s", settings.WEBAPP_HOST, settings.WEBAPP_PORT)
    await site.start()
    await asyncio.Event().wait()


async def main():
    mode = settings.BOT_MODE.lower()
    if mode == "webhook":
        if not settings.WEBHOOK_HOST:
            logger.error("WEBHOOK_HOST is required for webhook mode")
            sys.exit(1)
        await run_webhook()
    else:
        await run_polling()


if __name__ == "__main__":
    asyncio.run(main())
