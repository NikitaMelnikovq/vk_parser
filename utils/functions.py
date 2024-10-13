import aiohttp
import logging
import asyncpg

from db.database import db
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

VK_GROUP_API_URL = "https://api.vk.com/method/groups.getById"
API_VERSION = "5.154"

def check_nested_key(d, *keys):
    for key in keys:
        try:
            d = d[key]
        except (TypeError, KeyError):
            return None
    return d


def convert_time(date: datetime) -> int:
    return date.timestamp()


async def get_group_time(group_id: int):

    async with db.transaction():
        result = await db.scalar("SELECT date_added FROM user_groups WHERE group_id=$1", group_id)
        if result is None:
            return None
        return convert_time(result)


async def get_user_api_key(user_id):
    async with db.transaction():
        result = await db.first("SELECT API_KEY from users WHERE user_id=$1", user_id)
    return None if not result else result["api_key"]


async def check_link(link: str, user_id) -> bool:
    group_id = link.split("/")[-1]
    user_api_key = await get_user_api_key(user_id)

    url = f"{VK_GROUP_API_URL}?group_id={group_id}&access_token={user_api_key}&v=5.199"

    if group_id.startswith("club"):
        group_id = group_id.replace("club", "")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                print(data)
                return "response" in data
                
    except aiohttp.ClientError:
        return False


async def check_limit(user_id: int):
    print(f"Начата работа функции {check_limit.__name__}")

    try:
        async with db.transaction():
            authorized = await db.scalar("SELECT status FROM users WHERE user_id=$1", user_id)

            if authorized in ["in progress", "not authorized"]:
                return False
            
            subscribed = await db.scalar("SELECT subscribed FROM users WHERE user_id=$1", user_id)
            limit = 20 if subscribed else 3
            groups_count = await db.scalar(
                "SELECT COUNT(*) FROM users_groups_rel WHERE user_id=$1"
                ,user_id)

            return groups_count < limit

    except Exception:
        print(f"Произошла ошибка в функции {check_limit.__name__}. Проверьте логи ошибок.")
        return None


async def get_group_id(link: str, user_id: int):
    print(f"Начата работа функции {get_group_id.__name__}")

    group_id = link.split("/")[-1]
    user_api_key = await get_user_api_key(user_id)

    if group_id.startswith("club"):
        group_id = group_id.replace("club", "")
        return group_id
    else:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{VK_GROUP_API_URL}?group_id={group_id}&access_token={user_api_key}&v=5.199") as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data["response"]["groups"][0]["id"]

        except Exception:
            print(f"Произошла ошибка в функции {get_group_id.__name__}. Проверьте логи ошибок.")
            return None


async def get_group_name(group_id: int, user_id: int):
    user_api_key = await get_user_api_key(user_id)
    url = f"{VK_GROUP_API_URL}?group_id={group_id}&access_token={user_api_key}&v=5.199"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                return data["response"]["groups"][0]["name"]
            
    except KeyError:
        return None


async def add_group(user_id, link):
    group_id = await get_group_id(link, user_id)
    group_name = await get_group_name(group_id, user_id)

    try: 
        async with db.transaction():
            await db.status(
                """
                INSERT INTO user_groups (group_id, group_name)
                VALUES ($1, $2)
                ON CONFLICT (group_id, group_name) DO NOTHING;
                """,
                int(group_id), group_name
            )
            
            await db.status(
                """
                INSERT INTO users_groups_rel (user_id, group_id, group_name)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, group_id, group_name) DO NOTHING;
                """,
                int(user_id), int(group_id), group_name
            )

    except (
        asyncpg.exceptions.ProtocolViolationError, 
        asyncpg.exceptions.QueryCanceledError, 
        ValueError
    ) as e:
        logging.error(f"Произошла ошибка в функции {add_group.__name__}: {e}")
        return None


async def remove_group(user_id, link):
    group_id = await get_group_id(link)

    try:
        async with db.transaction():
            await db.status("DELETE FROM users_groups_rel WHERE user_id=$1 AND group_id=$2", user_id, group_id)
            return True
        
    except (
        asyncpg.exceptions.ProtocolViolationError, 
        asyncpg.exceptions.QueryCanceledError, 
        ValueError
    ) as e:
        logging.error(f"Произошла ошибка в функции {add_group.__name__}: {e}")
        return None
    

async def get_group_count():
    try:
        async with db.transaction():
            result = await db.scalar('SELECT COUNT(*) FROM user_groups')
            return result
        
    except (
        asyncpg.exceptions.ProtocolViolationError, 
        asyncpg.exceptions.QueryCanceledError, 
        ValueError
    ) as e:
        logging.error(f"Произошла ошибка в функции {add_group.__name__}: {e}")
        return None


async def get_api_keys():
        try:
            async with db.transaction():
                groups_count = await get_group_count()
                if not groups_count:
                    return None

                limit = int(groups_count / 20) if groups_count % 20 == 0 else int(groups_count / 20) + 1 
                rows = await db.all('SELECT api_key FROM users LIMIT $1', limit)
                api_keys = [row['api_key'] for row in rows]

                return api_keys
            
        except (
            asyncpg.exceptions.ProtocolViolationError, 
            asyncpg.exceptions.QueryCanceledError, 
            ValueError
        ) as e:
            logging.error(f"Произошла ошибка в функции {add_group.__name__}: {e}")
            return None
            

async def get_group_ids():
        try:
            async with db.transaction():
                groups = await db.all("SELECT * FROM user_groups")
                groups = [int(row['group_id']) for row in groups]

                return groups
        
        except (
            asyncpg.exceptions.ProtocolViolationError, 
            asyncpg.exceptions.QueryCanceledError, 
            ValueError
        ) as e:
            logging.error(f"Произошла ошибка в функции {add_group.__name__}: {e}")
            return None 