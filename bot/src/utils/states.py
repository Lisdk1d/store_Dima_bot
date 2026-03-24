from aiogram.fsm.state import State, StatesGroup


class ProductForm(StatesGroup):
    waiting_for_description = State()
    waiting_for_photo = State()
