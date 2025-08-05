from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

# Роутер для пользовательских команд и меню
router = Router()

# Главное меню пользователя (обычные кнопки)
main_menu = InlineKeyboardMarkup(
    inline_keyboard = [
        [InlineKeyboardButton(text="Моя профиль", callback_data="myprofile")],
        [InlineKeyboardButton(text="Начать чат с поддержкой", callback_data="help")],
        [InlineKeyboardButton(text="Ввести промокод", callback_data="promo")],
        [InlineKeyboardButton(text="Подробнее", callback_data="more_info"), InlineKeyboardButton(text="Моя история", callback_data="myhistory")]
    ],
    resize_keyboard=True
)
keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="profile")]
        ]
    )


@router.message(F.text == "/profile")
async def show_main_menu(message: Message):
    """
    Показывает главное меню пользователю при /start
    """
    await message.answer("Добро пожаловать! Выберите действие:", reply_markup=main_menu)

# Добавляйте новые обработчики для других кнопок и логики меню по мере необходимости
@router.callback_query(lambda c: c.data == "profile")
async def show_profile(callback: CallbackQuery):
    """
    Обработчик для кнопки "Мой профиль".
    Здесь можно добавить логику отображения профиля пользователя.
    """
    await callback.message.edit_text("Добро пожаловать! Выберите действие:", reply_markup=main_menu)