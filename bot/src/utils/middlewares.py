import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, Dict, Union

from fluentogram import TranslatorHub
from aiogram import BaseMiddleware
from aiogram.types import Update, Message
from cachetools import TTLCache
from motor.motor_asyncio import AsyncIOMotorClient

# from src.models.user import User

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
        language = data['user'].language_code if 'user' in data else 'ru'

        hub: TranslatorHub = data.get('t_hub')

        data['locale'] = hub.get_translator_by_locale(language)

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
        if not hasattr(event, "from_user") or event.from_user is None:
            return await handler(event, data)

        if event.from_user.id in caches["default"]:
            return
        caches["default"][event.from_user.id] = None
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
        self.latency = latency

    async def __call__(
            self,
            handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
            event: Any,
            data: dict[str, Any]
    ) -> Any:

        if not isinstance(event, Message):
            await handler(event, data)
            return

        message = event

        if not message.media_group_id:
            return await handler(message, data)
        try:
            self.album_data[message.media_group_id].append(message)
        except KeyError:
            self.album_data[message.media_group_id] = [message]
            await asyncio.sleep(self.latency)

            data['_is_last'] = True
            data["album"] = self.album_data[message.media_group_id]
            await handler(message, data)

        if message.media_group_id and data.get("_is_last"):
            del self.album_data[message.media_group_id]
            del data['_is_last']
