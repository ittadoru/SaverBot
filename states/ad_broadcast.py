from aiogram.fsm.state import StatesGroup, State


class AdBroadcastStates(StatesGroup):
    """Состояния для конструктора рекламной рассылки."""
    waiting_text = State()
    waiting_button_text = State()
    waiting_button_url = State()