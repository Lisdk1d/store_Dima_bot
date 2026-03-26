from aiogram.fsm.state import State, StatesGroup


class ProductForm(StatesGroup):
    waiting_for_category = State()
    waiting_for_model = State()
    waiting_for_description = State()
    waiting_for_price = State()
    waiting_for_photo = State()


class DeleteProcess(StatesGroup):
    waiting_for_del_model = State()
