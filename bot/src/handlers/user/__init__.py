__all__ = ("router", )

from aiogram import Router
from .message import router as message_router
from .callback import router as callback_router
from .checkout import router as checkout_router

router = Router()
router.include_routers(message_router, callback_router, checkout_router)
