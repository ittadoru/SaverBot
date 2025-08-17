from aiogram.fsm.state import StatesGroup, State


class Support(StatesGroup):
    waiting_for_question = State()  # Ожидание первого вопроса
    in_dialog = State()             # Пользователь находится в диалоге