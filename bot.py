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

logger = setup_logger()
load_dotenv()

bot = Bot(token=os.environ.get("BOT_TOKEN"))
dp = Dispatcher()

@dp.message(CommandStart())
async def start(msg: types.Message):
    async with get_db_connection() as conn:
        async with conn.transaction(isolation='serializable'):
            result = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", msg.from_user.id)
            if not result:
                await conn.execute("INSERT INTO users VALUES ($1)", msg.from_user.id)
                await msg.answer("Добро пожаловать!")
            else:
                await msg.answer("Добро пожаловать обратно!")
            
@dp.message(Command("help"))
async def help(msg: types.Message):
    await msg.answer("Здесь будет инструкция...")

@dp.message(Command("open_link"))
async def open_link(msg: types.Message):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(
        text="GitHub", url="https://github.com")
    )

    await msg.answer("Нажми кнопку ниже, чтобы открыть ссылку в браузере:", reply_markup=builder.as_markup())

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
