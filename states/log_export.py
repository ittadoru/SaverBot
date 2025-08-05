from aiogram.fsm.state import State, StatesGroup


class LogExport(StatesGroup):
    waiting_for_date = State()

