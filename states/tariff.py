from aiogram.filters import StateFilter
from aiogram.fsm.state import StatesGroup, State


class TariffStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_days = State()
    waiting_for_price = State()