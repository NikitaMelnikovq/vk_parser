from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="/authorize")
        ],
        [
            KeyboardButton(text="/updates_on"),
            KeyboardButton(text="/updates_off")
        ],
        [
            KeyboardButton(text="/add_group"),
            KeyboardButton(text="/remove_group")
        ],
        [
            KeyboardButton(text="/get_group_list")
        ]
    ],
    resize_keyboard=True
)

