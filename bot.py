import asyncio
import json
import logging
import os

import aio_pika
from aiogram import Bot, Dispatcher, Router
from dotenv import load_dotenv
from datetime import datetime

from bot_router import setup_routes
from db.database import db, init_db, close_db

class BotApp:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_token = os.environ.get("BOT_TOKEN")
        self.fastapi_url = os.environ.get("FASTAPI_URL")
        self.rabbitmq_url = os.environ.get("RABBITMQ_URL")

        self.bot = Bot(token=self.api_token)
        self.dp = Dispatcher()
        self.router = Router()
        setup_routes(self.router)
        self.dp.include_router(self.router)

    async def start_polling(self):
        await init_db()
        try:
            consumer_task = asyncio.create_task(self.consume_messages())
            await self.dp.start_polling(self.bot)
            await consumer_task
        except Exception as e:
            self.logger.exception("Ошибка во время работы основного процесса")
        finally:
            await close_db()

    async def send_messages(self, text: str, group_id: int):
        """
        Отправка сообщений всем авторизованным пользователям.
        """
        try:
            async with db.transaction():
                user_ids = await db.all("SELECT user_id FROM users_groups_rel WHERE group_id = $1", group_id)
                chat_ids = [
                    (await db.first("SELECT chat_id FROM users WHERE user_id = $1", user_id))[0]
                    for (user_id,) in user_ids if user_id
                ]

            send_tasks = [self.bot.send_message(chat_id=chat_id, text=text) for chat_id in chat_ids]
            results = await asyncio.gather(*send_tasks, return_exceptions=True)

            for chat_id, result in zip(chat_ids, results):
                if isinstance(result, Exception):
                    self.logger.error(f"Не удалось отправить сообщение пользователю {chat_id}: {result}")
                else:
                    self.logger.info(f"Сообщение успешно отправлено пользователю {chat_id}.")
        except Exception:
            self.logger.exception("Ошибка при отправке сообщений")

    async def process_message(self, message: aio_pika.IncomingMessage):
        """
        Обработка одного сообщения из очереди RabbitMQ.
        """
        async with message.process():
            try:
                data = json.loads(message.body.decode())
                text = f"""
                    {datetime.fromisoformat(data['post_date'])}
                    {data['group_name']}
                    {data['post_text']}
                    {data['post_link']}
                """.strip()
                await self.send_messages(text, data['group_id'])
            except Exception:
                self.logger.exception("Ошибка при обработке сообщения")

    async def consume_messages(self):
        """
        Подключение к RabbitMQ и потребление сообщений.
        """
        while True:
            try:
                connection = await aio_pika.connect_robust(self.rabbitmq_url)
                async with connection:
                    channel = await connection.channel()
                    await channel.set_qos(prefetch_count=10)
                    queue = await channel.declare_queue("posts_queue", durable=True)
                    self.logger.info("Подключено к очереди posts_queue в RabbitMQ.")

                    async with queue.iterator() as queue_iter:
                        async for message in queue_iter:
                            await self.process_message(message)
            except Exception:
                self.logger.exception("Ошибка подключения или потребления сообщений, повторная попытка через 5 секунд")
                await asyncio.sleep(5)


async def main():
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    app = BotApp()
    await app.start_polling()


if __name__ == "__main__":
    asyncio.run(main())
