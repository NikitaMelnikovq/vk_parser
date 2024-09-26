from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

button = InlineKeyboardButton(text="Перейти на сайт", url="http://95.164.69.218:8000/login")
inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])