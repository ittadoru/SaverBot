from aiogram.fsm.state import StatesGroup, State

class Broadcast(StatesGroup):
    waiting_for_message = State()
