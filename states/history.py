from aiogram.fsm.state import StatesGroup, State


class HistoryStates(StatesGroup):
    waiting_for_id_or_username = State()
    waiting_grant_amount = State()
    waiting_grant_message = State()
