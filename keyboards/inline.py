from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

button = InlineKeyboardButton(text="Перейти на сайт", url="")
inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])