from aiogram.fsm.state import StatesGroup, State


class AdBroadcastStates(StatesGroup):
    waiting_text = State()