import asyncio
import json
import logging
import os

import aio_pika
from aiogram import Bot, Dispatcher, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command, CommandStart
from dotenv import load_dotenv
from aiogram.types import CallbackQuery

from bot_router import router
from db.database import db
from db.database import init_db, close_db
from keyboards.keyboard import keyboard

load_dotenv()

FASTAPI_URL = os.environ.get("FASTAPI_URL")
logger = logging.getLogger(__name__)
RABBITMQ_URL = os.environ.get("RABBITMQ_URL")

bot = Bot(token=os.environ.get("BOT_TOKEN"))
dp = Dispatcher()

@dp.message(CommandStart())
async def start(msg: types.Message):
    async with db.transaction():
        result = await db.first("SELECT * FROM users WHERE user_id=$1", msg.from_user.id)
        if not result:
            await db.status("INSERT INTO users (user_id, user_limit, status, chat_id) VALUES ($1, $2, 'not_authorized', $3)", msg.from_user.id, 0, msg.chat.id)
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
    async with db.transaction():
        db.status("UPDATE users SET status = 'in progress' WHERE user_id = $2", query.from_user.id)


@dp.message(Command("get_chat_id"))
async def get_chat_id(msg: types.Message):
    await msg.answer(str(msg.chat.id))


async def consume_messages(bot: Bot):
    """
    Подключение к RabbitMQ и потребление сообщений.
    """
    while True:
        try:
            connection = await aio_pika.connect_robust(RABBITMQ_URL)
            async with connection:
                channel = await connection.channel()
                # Установка QoS для контроля количества одновременно обрабатываемых сообщений
                await channel.set_qos(prefetch_count=10)
                queue = await channel.declare_queue(QUEUE_NAME, durable=True)
                logger.info(f"Подключено к очереди '{QUEUE_NAME}' в RabbitMQ.")

                async with queue.iterator() as queue_iter:
                    async for message in queue_iter:
                        await process_message(message, bot)

        except Exception as e:
            logger.exception(f"Ошибка подключения или потребления сообщений: {e}")
            logger.info("Повторная попытка подключения через 5 секунд...")
            await asyncio.sleep(5)  # Ожидание перед повторным подключением

async def main():
    try:
        await init_db()


        consumer_task = asyncio.create_task(consume_messages(bot))

        # connection = await aio_pika.connect_robust(
        #     "amqp://guest:guest@localhost/"
        # )

        # async with connection:
        #     channel = await connection.channel()
        #     queue = await channel.declare_queue('your_queue_name', durable=True)

        #     async with queue.iterator() as queue_iter:
        #         async for message in queue_iter:
        #             async with message.process():
        #                 body = message.body.decode()
        #                 data = json.loads(body)
        #                 text = f"""
        #                     {data['post_date']}
        #                     {data['group_name']}
        #                     {data['post_text']}
        #                     {data['post_link']}
        #                 """

        #                 async with db.transaction():
        #                     user_ids = await db.fetch("SELECT user_id FROM users_groups_rel WHERE group_id = $1", data['group_id'])

        #                     chat_ids = []
        #                     for user_id in user_ids:
        #                         chat_id = await db.fetchval("SELECT chat_id FROM users WHERE user_id = $1", user_id)
        #                         chat_ids.append(chat_id)

        #                     for chat_id in chat_ids:
        #                         await bot.send_message(chat_id, text)

        logging.basicConfig(level=logging.INFO)
        
        dp.include_router(router)

        await dp.start_polling(bot)
        
    except Exception as e:
        print(e)
    finally:
        await close_db()
        

if __name__ == "__main__":
    asyncio.run(main())