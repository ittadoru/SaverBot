from aiogram.fsm.state import State, StatesGroup


class PromoStates(StatesGroup):
    add = State()      # ожидание ввода промокода и срока
    remove = State()   # ожидание ввода промокода для удаления
    user = State()     # ожидание ввода промокода от пользователя
