from aiogram.fsm.state import State, StatesGroup


class ProductForm(StatesGroup):
    waiting_for_category = State()
    waiting_for_model = State()
    waiting_for_description = State()
    waiting_for_price = State()
    waiting_for_photo = State()


class EditProductForm(StatesGroup):
    waiting_for_model = State()
    waiting_for_field = State()
    waiting_for_new_value = State()
    waiting_for_new_photo = State()


class DeleteProcess(StatesGroup):
    waiting_for_del_model = State()


class DeleteCategoryProcess(StatesGroup):
    waiting_for_category = State()


class CheckoutProcess(StatesGroup):
    """Cart or single-product checkout: quantity → delivery → payment."""
    waiting_for_quantity = State()
    waiting_for_address = State()
    waiting_for_payment = State()
