from aiogram import Bot, Dispatcher, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import CommandStart, Command
from dotenv import load_dotenv
from bot_router import router
from db.connection_manager import get_db_connection
from db.database import init_pool, close_pool
import asyncio
import logging
import os
from logger.logger import setup_logger
from aiogram.types import CallbackQuery
from keyboards.keyboard import keyboard

logger = setup_logger()
load_dotenv()

FASTAPI_URL = 'http://localhost:8000/login'

bot = Bot(token=os.environ.get("BOT_TOKEN"))
dp = Dispatcher()

@dp.message(CommandStart())
async def start(msg: types.Message):
    async with get_db_connection() as conn:
        async with conn.transaction(isolation='read_committed'):
            result = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", msg.from_user.id)
            if not result:
                await conn.execute("INSERT INTO users (user_id, user_limit, status) VALUES ($1, $2, 'not_authorized')", msg.from_user.id, 0)
                await msg.answer("Добро пожаловать!", reply_markup=keyboard)
            else:
                await msg.answer("Добро пожаловать обратно!", reply_markup=keyboard)
            
@dp.message(Command("help"))
async def help(msg: types.Message):
    await msg.answer("""
    Добро пожаловать в бота для отслеживания новых постов в группах ВК!
    Список доступных команд:
        /start - начать работу с ботом
        /help - помощь
        /authorize - авторизоваться через ВК
        /add_group - добавить группу
        /remove_group - удалить группу
        /updates_on - подключить уведомления 
        /updates_off - отключить уведомления
""", reply_markup=keyboard)

@dp.message(Command("authorize"))
async def open_link(msg: types.Message):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(
        text="Авторизоваться", url=f"{FASTAPI_URL}?user_id={msg.from_user.id}", callback_data="auth")
    )

    await msg.answer("Авторизуйтесь через ВК:", reply_markup=builder.as_markup())

@dp.callback_query(lambda query: query.data == "auth" and query.data.startswith("auth"))
async def open_github_link(query: CallbackQuery):
    async with get_db_connection() as conn:
        async with conn.transaction(isolation="read_committed"):
            conn.execute("UPDATE users SET status = 'in progress' WHERE user_id = $2", query.from_user.id)

async def main():
    try:
        await init_pool()
        logging.basicConfig(level=logging.INFO)
        dp.include_router(router)
        await dp.start_polling(bot)
    except Exception as e:
        print(e)
    finally:
        await close_pool()
        
if __name__ == "__main__":
    asyncio.run(main())
