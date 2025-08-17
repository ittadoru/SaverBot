from aiogram.fsm.state import State, StatesGroup


class BroadcastStates(StatesGroup):
    """Состояния для конструктора общей рассылки."""
    waiting_text = State()
    waiting_button_text = State()
    waiting_button_url = State()