from aiogram.fsm.state import StatesGroup, State

class AdBroadcastStates(StatesGroup):
    waiting_text = State()
    waiting_button_choice = State()
    waiting_button_text = State()
    waiting_button_url = State()