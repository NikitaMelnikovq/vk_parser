import aiohttp
import logging
import os

from datetime import datetime
from dotenv import load_dotenv
from cryptography.fernet import Fernet

from db.database import db


load_dotenv()
logger = logging.getLogger(__name__)

VK_GROUP_API_URL = "https://api.vk.com/method/groups.getById"
API_VERSION = "5.154"

def decrypt_token(encrypted_token: str) -> str:
    encryption_key = os.getenv("ENCRYPTION_KEY")
    cipher = Fernet(encryption_key)
    return cipher.decrypt(encrypted_token.encode()).decode()


def calculate_limit(group_count: int, subscribed: bool) -> int:
    limit = 20 if subscribed else 3
    return limit if group_count < limit else 0


def check_nested_key(d, *keys) -> dict:
    for key in keys:
        try:
            d = d[key]
        except (TypeError, KeyError):
            return None
    return d


def convert_date_to_msec(date: datetime) -> int:
    return date.timestamp()

def convert_msec_to_date(msec: int) -> datetime:
    return datetime.fromtimestamp(msec)


async def get_group_time(group_id: int) -> int:
    async with db.transaction():
        result = await db.scalar("SELECT date_added FROM user_groups WHERE group_id=$1", group_id)
        if result is None:
            return None
        return convert_date_to_msec(result)


async def get_user_api_key(user_id):
    async with db.transaction():
        result = await db.first("SELECT API_KEY from users WHERE user_id=$1", user_id)

    return None if not result else decrypt_token(result["api_key"])


async def check_link(link: str, user_id) -> bool:
    group_id = link.split("/")[-1]
    user_api_key = await get_user_api_key(user_id)

    url = f"{VK_GROUP_API_URL}?group_id={group_id}&access_token={user_api_key}&v=5.199"

    if group_id.startswith("club"):
        group_id = group_id.replace("club", "")

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response.raise_for_status()
            data = await response.json()
            return "response" in data

async def check_limit(user_id: int) -> bool:
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


async def get_group_id(link: str, user_id: int) -> int:

    group_id = link.split("/")[-1]

    if group_id.startswith("club"):
        group_id = group_id.replace("club", "")
        return group_id
    
    user_api_key = await get_user_api_key(user_id)

    url = (
        f"{VK_GROUP_API_URL}?group_id={group_id}"
        f"&access_token={user_api_key}&v=5.199"
    )


    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                return None

            data = await response.json()

            return data["response"]["groups"][0]["id"]



async def get_group_name_from_db(group_id: int) -> str:
    async with db.transaction():
        result = await db.first("SELECT group_name FROM user_groups WHERE group_id=$1", group_id)
        return result["group_name"]


async def get_group_name(group_id: int, user_id: int) -> str:
    user_api_key = await get_user_api_key(user_id)

    url = (
        f"{VK_GROUP_API_URL}?group_id={group_id}"
        f"&access_token={user_api_key}&v=5.199"
    )

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                return None

            data = await response.json()

            return data["response"]["groups"][0]["name"]
        

async def add_group(user_id, link) -> bool:
    try:
        group_id = await get_group_id(link, user_id)
        group_name = await get_group_name(group_id, user_id)
    except (aiohttp.ClientError, KeyError) as e:
        logging.error("Произошла ошибка при добавлении группы. Текст ошибки: %s", e)
        return False 

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
            INSERT INTO users_groups_rel (user_id, group_id)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id, group_id) DO NOTHING;
            """,
            int(user_id), int(group_id)
        )
        
        return True


async def remove_group(user_id, link) -> bool:
    try:
        group_id = await get_group_id(link)
    except (aiohttp.ClientError, KeyError) as e:
        logging.error("Произошла ошибка при удалении группы. Текст ошибки: %s", e)
        return False
    
    async with db.transaction():
        await db.status("DELETE FROM users_groups_rel WHERE user_id=$1 AND group_id=$2", user_id, group_id)

        groups_count = await db.scalar("SELECT COUNT(*) FROM users_groups_rel WHERE user_id=$1", user_id)

        if groups_count == 0:
            await db.status("DELETE FROM user_grops WHERE group_id=$1", group_id)
            
        return True


async def get_group_count() -> int:
    async with db.transaction():
        result = await db.scalar('SELECT COUNT(*) FROM user_groups')

        return result


async def get_api_keys() -> list:
        async with db.transaction():
            groups_count = await get_group_count()

            if not groups_count:
                return None

            limit = int(groups_count / 20) if groups_count % 20 == 0 else int(groups_count / 20) + 1 
            rows = await db.all('SELECT api_key FROM users LIMIT $1', limit)
            api_keys = [decrypt_token(row['api_key']) for row in rows]

            return api_keys
            

async def get_group_ids() -> list:
    async with db.transaction():
        groups = await db.all("SELECT * FROM user_groups")
        groups = [int(row['group_id']) for row in groups]

        return groups