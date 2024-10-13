import logging 
import asyncio 
import traceback

import aiohttp
import schedule
import asyncpg

from db.database import close_db, db, init_db
from utils.functions import check_nested_key, get_api_keys, get_group_ids, get_group_time


async def add_data_to_db(group_data: dict, group_id: int):
        logging.INFO("Добавление данных в базу данных")

        post_id = group_data["id"]
        post_text = group_data["text"]
        post_date = group_data["date"]
        post_link = f"https://vk.com/wall-{group_id}_{post_id}"

        try:
            async with db.transaction():
                result = await db.scalar(
                    "SELECT * FROM cached_post_ids WHERE post_id=$1", post_id
                    )
                if result is not None:
                    return
                
                await db.status(
                    "INSERT INTO cached_post_ids VALUES ($1)", post_id
                    )
                await db.status(
                    "INSERT INTO posts VALUES ($1, $2, $3, $4, $5)",
                    post_id, post_text, post_link, post_date
                )

        except (asyncpg.exceptions.ProtocolViolationError, asyncpg.exceptions.QueryCanceledError, ValueError):
            logging.error(f"Произошла ошибка в функции {add_data_to_db.__name__}")
            return None
        
        logging.INFO("Данные успешно добавлены в базу данных")

async def get_group_data(group_id, api_key):
    date = await get_group_time(group_id)

    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://api.vk.com/method/wall.get?owner_id=-{group_id}&count=3&"
            f"access_token={api_key}&v=5.199"
        ) as response:
            if response.status != 200:
                logging.error("Error fetching data in get_group_data")
                return
            await asyncio.sleep(3)

            is_valid = check_nested_key(await response.json(), "response", "items")
            if not is_valid:
                return None
            
            posts = await response.json()
            posts = posts["response"]["items"]

            for post in posts:
                if post["date"] < date:
                    continue

                await add_data_to_db(post, group_id)
            

async def start_parsing(api_keys, groups):
    group_key_mapping = {}
    current_key_index = 0
    usage_per_key = 20

    for i, group in enumerate(groups):
        key = api_keys[current_key_index]
        group_key_mapping[group] = key
        if (i + 1) % usage_per_key == 0:
            current_key_index += 1
    
    for group_id, api_key in group_key_mapping.items():
        await get_group_data(group_id, api_key)



async def execute():
    api_keys = await get_api_keys()
    groups = await get_group_ids()
    if not api_keys:
        logging.info("Не удалось получить список ключей")
        return 
    if not groups:
        print("Не удалось получить список групп")
        return
    await start_parsing(api_keys, groups)

def schedule_task():
    loop = asyncio.get_event_loop()
    loop.create_task(execute())

async def scheduler():
    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

async def main():
    try:
        await init_db()
        schedule.every(1).minutes.do(schedule_task)
        
        await scheduler()
    except Exception as e:
        print(f"Ошибка в файле vk_parser в методе main, ошибка: {traceback.print_exc()}",)
    finally:
        await close_db()

if __name__ == "__main__":
    asyncio.run(main())

