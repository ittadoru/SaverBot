from aiogram.fsm.state import StatesGroup, State

class Support(StatesGroup):
    waiting_for_message = State()