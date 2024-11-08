import aiohttp
import logging
import os

from datetime import datetime
from dotenv import load_dotenv
from cryptography.fernet import Fernet
from typing import Any, Optional, List

from db.database import db


load_dotenv()
logger = logging.getLogger(__name__)

VK_GROUP_API_URL = "https://api.vk.com/method/groups.getById"
API_VERSION = "5.154"


def decrypt_token(encrypted_token: str) -> str:
    """Дешифрует зашифрованный токен пользователя."""
    encryption_key = os.getenv("ENCRYPTION_KEY")
    cipher = Fernet(encryption_key)
    return cipher.decrypt(encrypted_token.encode()).decode()


def calculate_limit(group_count: int, subscribed: bool) -> int:
    """Вычисляет лимит групп для пользователя в зависимости от его статуса подписки."""
    limit = 20 if subscribed else 3
    return limit if group_count < limit else 0


def check_nested_key(d: dict, *keys) -> Optional[Any]:
    """Проверяет наличие вложенных ключей в словаре."""
    for key in keys:
        try:
            d = d[key]
        except (TypeError, KeyError):
            return None
    return d


def convert_date_to_sec(date: datetime) -> int:
    """Преобразует объект datetime в количество секунд с начала эпохи UNIX."""
    return int(date.timestamp())


def convert_sec_to_date(sec: int) -> datetime:
    """Преобразует время в секундах в объект datetime."""
    return datetime.fromtimestamp(sec)


async def get_group_time(group_id: int) -> Optional[int]:
    """Получает время добавления группы по ее идентификатору."""
    async with db.transaction():
        result = await db.scalar(
            "SELECT date_added FROM user_groups WHERE group_id=$1", group_id
        )
        if result is None:
            return None
        return convert_date_to_sec(result)


async def get_user_api_key(user_id: int) -> Optional[str]:
    """Получает и расшифровывает API-ключ пользователя."""
    async with db.transaction():
        result = await db.first(
            "SELECT api_key FROM users WHERE user_id=$1", user_id
        )
    return None if not result else decrypt_token(result["api_key"])


async def check_link(link: str, user_id: int) -> bool:
    """Проверяет, существует ли группа по указанной ссылке."""
    group_id = link.split("/")[-1]
    user_api_key = await get_user_api_key(user_id)

    if group_id.startswith("club"):
        group_id = group_id.replace("club", "")

    url = (
        f"{VK_GROUP_API_URL}?group_id={group_id}"
        f"&access_token={user_api_key}&v={API_VERSION}"
    )

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response.raise_for_status()
            data = await response.json()
            return "response" in data


async def check_limit(user_id: int) -> bool:
    """Проверяет, достиг ли пользователь лимита на количество групп."""
    async with db.transaction():
        authorized = await db.scalar(
            "SELECT status FROM users WHERE user_id=$1", user_id
        )

        if authorized in ["in progress", "not authorized"]:
            return False

        subscribed = await db.scalar(
            "SELECT subscribed FROM users WHERE user_id=$1", user_id
        )
        limit = 20 if subscribed else 3
        groups_count = await db.scalar(
            "SELECT COUNT(*) FROM users_groups_rel WHERE user_id=$1", user_id
        )

        return groups_count < limit


async def get_group_id(link: str, user_id: int) -> Optional[int]:
    """Получает идентификатор группы из ссылки или через VK API."""
    group_id = link.split("/")[-1]

    if group_id.startswith("club"):
        group_id = group_id.replace("club", "")
        return int(group_id)

    user_api_key = await get_user_api_key(user_id)

    url = (
        f"{VK_GROUP_API_URL}?group_id={group_id}"
        f"&access_token={user_api_key}&v={API_VERSION}"
    )

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                return None

            data = await response.json()
            return data["response"][0]["id"]


async def get_group_name_from_db(group_id: int) -> Optional[str]:
    """Получает имя группы из базы данных по ее идентификатору."""
    async with db.transaction():
        result = await db.first(
            "SELECT group_name FROM user_groups WHERE group_id=$1", group_id
        )
        return result["group_name"] if result else None


async def get_group_name(group_id: int, user_id: int) -> Optional[str]:
    """Получает имя группы через VK API по идентификатору группы."""
    user_api_key = await get_user_api_key(user_id)

    url = (
        f"{VK_GROUP_API_URL}?group_id={group_id}"
        f"&access_token={user_api_key}&v={API_VERSION}"
    )

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                return None

            data = await response.json()
            return data["response"][0]["name"]


async def add_group(user_id: int, link: str) -> bool:
    """Добавляет группу в базу данных и связывает ее с пользователем."""
    try:
        group_id = await get_group_id(link, user_id)
        group_name = await get_group_name(group_id, user_id)
    except (aiohttp.ClientError, KeyError, TypeError) as e:
        logger.error("Произошла ошибка при добавлении группы. Текст ошибки: %s", e)
        return False

    async with db.transaction():
        await db.status(
            """
            INSERT INTO user_groups (group_id, group_name)
            VALUES ($1, $2)
            ON CONFLICT (group_id) DO NOTHING;
            """,
            int(group_id), group_name
        )

        await db.status(
            """
            INSERT INTO users_groups_rel (user_id, group_id)
            VALUES ($1, $2)
            ON CONFLICT (user_id, group_id) DO NOTHING;
            """,
            int(user_id), int(group_id)
        )

        return True


async def remove_group(user_id: int, link: str) -> bool:
    """Удаляет группу из базы данных и разрывает связь с пользователем."""
    try:
        group_id = await get_group_id(link, user_id)
    except (aiohttp.ClientError, KeyError, TypeError) as e:
        logger.error("Произошла ошибка при удалении группы. Текст ошибки: %s", e)
        return False

    async with db.transaction():
        await db.status(
            "DELETE FROM users_groups_rel WHERE user_id=$1 AND group_id=$2",
            user_id, group_id
        )

        groups_count = await db.scalar(
            "SELECT COUNT(*) FROM users_groups_rel WHERE group_id=$1", group_id
        )

        if groups_count == 0:
            await db.status(
                "DELETE FROM user_groups WHERE group_id=$1", group_id
            )

        return True


async def get_group_count() -> int:
    """Возвращает количество групп в базе данных."""
    async with db.transaction():
        result = await db.scalar("SELECT COUNT(*) FROM user_groups")
        return result


async def get_api_keys() -> Optional[List[str]]:
    """Получает список API-ключей для авторизованных пользователей."""
    async with db.transaction():
        groups_count = await get_group_count()

        if not groups_count:
            return None

        limit = (
            groups_count // 20 if groups_count % 20 == 0 else (groups_count // 20) + 1
        )
        rows = await db.all(
            "SELECT api_key FROM users WHERE status = 'authorized' LIMIT $1", limit
        )
        api_keys = [decrypt_token(row["api_key"]) for row in rows]

        return api_keys


async def get_group_ids() -> List[int]:
    """Возвращает список идентификаторов всех групп."""
    async with db.transaction():
        groups = await db.all("SELECT group_id FROM user_groups")
        return [int(row["group_id"]) for row in groups]


async def get_group_names() -> List[str]:
    """Возвращает список имен всех групп."""
    async with db.transaction():
        groups = await db.all("SELECT group_name FROM user_groups")
        return [row["group_name"] for row in groups]
