import aiohttp
import asyncio 
import logging
import schedule
from db.connection_manager import get_db_connection
from db.database import init_pool, close_pool
from utils.functions import get_api_keys, get_group_list, check_nested_key, convert_time
from logger.logger import setup_logger

logger = setup_logger()


async def add_data_to_db(group_data: dict, group_id: int):
        post_id = group_data["id"]
        post_text = group_data["text"]
        post_date = group_data["date"]
        post_link = f"https://vk.com/wall-{group_id}_{post_id}"
        date = convert_time(post_date)

        async with get_db_connection() as conn, conn.transaction(isolation="read_committed"):
            result = await conn.fetchval("SELECT * FROM cached_post_ids WHERE post_id=$1", post_id)
            if result is not None:
                return
            await conn.execute("INSERT INTO cached_post_ids VALUES ($1)", post_id)
            await conn.execute("INSERT INTO posts VALUES ($1, $2, $3, $4, $5)", post_id, post_text, post_link, date)

async def get_droup_data(group_id, api_key):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.vk.com/method/wall.get?owner_id=-{group_id}&count={3}&access_token={api_key}&v=5.199") as response:
            if response.status != 200:
                print("Произошла ошибка при получении данных в функции get_droup_data")
                return
            asyncio.sleep(3)
            is_valid = check_nested_key(response.json(), "response", "items")
            if not is_valid:
                return -1 
            posts = response.json()["response"]["items"]
            for post in posts:
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
        await get_droup_data(group_id, api_key)


async def execute():
    api_keys = await get_api_keys()
    groups = await get_group_list()
    if api_keys == -1:
        print("Не удалось получить API ключи")
        return
    if groups == -1:
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
        await init_pool()
        logging.basicConfig(level=logging.INFO)
        schedule.every(10).minutes.do(schedule_task)
        await scheduler()
    except Exception as e:
        print(e)
        print("Ошибка в файле vk_parser в методе main")
    finally:
        await close_pool()

if __name__ == "__main__":
    asyncio.run(main())

