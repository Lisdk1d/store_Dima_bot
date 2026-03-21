from aiogram import Router, Bot
from aiogram.types import CallbackQuery
from fluentogram import TranslatorRunner

router = Router()


@router.callback_query(lambda c: c.data == "reviews")
async def show_reviews(callback: CallbackQuery,
                       bot: Bot,
                       locale: TranslatorRunner):

    await callback.message.answer(locale.reviews_callback())


@router.callback_query(lambda c: c.data == "address")
async def show_reviews(callback: CallbackQuery,
                       bot: Bot,
                       locale: TranslatorRunner):

    await callback.message.answer(locale.locale_callback())


@router.callback_query(lambda c: c.data == "delivery")
async def show_reviews(callback: CallbackQuery,
                       bot: Bot,
                       locale: TranslatorRunner):

    await callback.message.answer(locale.trans_callback())
