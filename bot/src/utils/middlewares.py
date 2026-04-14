import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, Union

from fluentogram import TranslatorHub
from aiogram import BaseMiddleware
from aiogram.types import Update, Message
from cachetools import TTLCache
from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

caches = {
    "default": TTLCache(maxsize=10_000, ttl=0.1)
}


class TranslateMiddleware(BaseMiddleware):  # pylint: disable=too-few-public-methods
    """
    Fluentogram translation middleware
    """

    async def __call__(
            self,
            handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
            event: Update,
            data: Dict[str, Any]
    ) -> Any:
        user = data.get("user")
        locale_code = getattr(user, "language_code", "ru")

        hub: TranslatorHub | None = data.get("t_hub")
        if hub is None:
            logging.error("Translator hub is missing in middleware data")
            return await handler(event, data)

        try:
            data["locale"] = hub.get_translator_by_locale(locale_code)
        except Exception as error:
            # Fallback keeps bot operational even for unknown locale values.
            logging.exception("Failed to resolve translator for locale '%s': %s", locale_code, error)
            data["locale"] = hub.get_translator_by_locale("ru")

        return await handler(event, data)


class ThrottlingMiddleware(BaseMiddleware):  # pylint: disable=too-few-public-methods
    """
    Throttling middleware
    """

    async def __call__(
            self,
            handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
            event: Update,
            data: Dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user is None:
            return await handler(event, data)

        user_id = user.id
        throttle_cache = caches["default"]
        if user_id in throttle_cache:
            return
        throttle_cache[user_id] = None
        return await handler(event, data)


class DataBaseMiddleware(BaseMiddleware):  # pylint: disable=too-few-public-methods
    """
    Data base middleware
    """

    def __init__(self, db: AsyncIOMotorClient):
        super().__init__()
        self.db = db

    async def __call__(
            self,
            handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
            event: Update,
            data: Dict[str, Any],
    ) -> Any:
        data["db"] = self.db
        return await handler(event, data)


class AlbumMiddleware(BaseMiddleware):  # pylint: disable=too-few-public-methods
    """
    Waiting for all pictures in media group will be uploaded
    """
    album_data: dict = {}

    def __init__(self, latency: Union[int, float] = 0.6):
        super().__init__()
        self.latency = latency

    async def __call__(
            self,
            handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
            event: Any,
            data: dict[str, Any]
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        message = event

        if not message.media_group_id:
            return await handler(message, data)
        try:
            self.album_data[message.media_group_id].append(message)
        except KeyError:
            self.album_data[message.media_group_id] = [message]
            await asyncio.sleep(self.latency)

            data["_is_last"] = True
            data["album"] = self.album_data[message.media_group_id]
            await handler(message, data)

        if message.media_group_id and data.get("_is_last"):
            self.album_data.pop(message.media_group_id, None)
            data.pop("_is_last", None)
