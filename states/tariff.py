from aiogram.fsm.state import StatesGroup, State


class TariffStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_days = State()
    waiting_for_price = State()
    # Editing
    editing_select_field = State()
    editing_new_value = State()