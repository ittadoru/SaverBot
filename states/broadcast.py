from aiogram.fsm.state import StatesGroup, State

class Broadcast(StatesGroup):
    waiting_for_message = State()
    waiting_button_choice = State()
    waiting_button_text = State()
    waiting_button_url = State()