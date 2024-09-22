import aiohttp
import os
from db.connection_manager import get_db_connection
from datetime import datetime

async def check_link(link: str) -> bool:
    if not link.startswith("https://vk.com/"):
        return False

    group_id = link.split("/")[-1]
    if group_id.startswith("club"):
        group_id = group_id.replace("club", "")

    url = f"https://api.vk.com/method/groups.getById?group_id={group_id}&access_token={os.environ.get('API_KEY')}&v=5.199"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                return "response" in data
        except aiohttp.ClientError:
            return False
        
async def get_group_id(url: str) -> int:
    group_id = url.split("/")[-1]
    if group_id.startswith("club"):
        group_id = group_id.replace("club", "")
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"https://api.vk.com/method/groups.getById?group_id={group_id}&access_token={os.environ.get('API_KEY')}&v=5.154") as group:
                if group.status == 200:
                    group = await group.json()
                    group_id = group["response"]["groups"][0]["id"]
        except KeyError:
            print("Ошибка получения группы. Проверьте правильность ссылки")
        except Exception as e:
            print(e)     
    return group_id

async def check_limit(user_id: int):
    async with get_db_connection() as conn:
        async with conn.transaction(isolation="read_committed"):
            count = await conn.fetchval("SELECT COUNT(*) FROM subscriptions WHERE user_id=$1", user_id)
            limit = 3
            if count == 1:
                limit = 20
            user_groups_count = await conn.fetchval("SELECT COUNT(*) FROM users_groups WHERE user_id=$1", user_id)
            return user_groups_count < limit

async def add_group(user_id, link):
    group_id = await get_group_id(link)
    async with get_db_connection() as conn:
        async with conn.transaction(isolation="read_committed"):
            try: 
                await conn.execute("""
                                        INSERT INTO groups (group_id)
                                        SELECT $1
                                        WHERE NOT EXISTS (
                                            SELECT 1 FROM groups WHERE group_id = $1
                                        );
                                    """, group_id)
                await conn.execute("""
                                        INSERT INTO users_groups (user_id, group_id)
                                        SELECT $1, $2
                                        WHERE NOT EXISTS (
                                            SELECT 1 FROM users_groups WHERE user_id = $1 AND group_id = $2
                                        );
                                    """, user_id, group_id)
                return 1
            except Exception as e:
                print(e)
                return 0
            
async def get_group_count():
    async with get_db_connection() as conn:
        async with conn.transaction(isolation="read_committed"):
            try:
                result = await conn.fetchval('SELECT COUNT(*) FROM your_table')
                return result
            except Exception as e:
                print(e)
                print("Exception occured in file functions.py in get_group_count function")
                return -1

async def get_api_keys():
    async with get_db_connection() as conn:
        async with conn.transaction(isolation="read_committed"):    
            try:
                groups_count = await get_group_count()
                if groups_count == -1:
                    return -1
                limit = int(groups_count / 20) if groups_count % 20 == 0 else int(groups_count / 20) + 1 
                rows = await conn.fetch('SELECT api_key FROM users LIMIT $1', limit)
                api_keys = [row['api_key'] for row in rows]
                return api_keys
            except Exception as e:
                print(e)
                print("Exception occured in file functions.py in get_api_keys function")
                return -1
            
async def get_group_list():
     async with get_db_connection() as conn:
        async with conn.transaction(isolation="read_committed"):
            try:
                groups = await conn.fetch("SELECT group_id FROM groups")
                groups = [row['group_id'] for row in groups]
                return groups
            except Exception as e:
                print("Exception occured in get_group_list (functions.py)")
                print(e)
                return -1 
            
def check_nested_key(d, *keys):
    for key in keys:
        try:
            d = d[key]
        except (TypeError, KeyError):
            return None
    return d

def convert_time(timestamp: int) -> str:
    date = datetime.fromtimestamp(timestamp)
    return date.strftime('%Y-%m-%d %H:%M:%S')

async def get_user_id(url: str):
    user_id = url.split("/")[-1]
    if user_id.startswith("id"):
        user_id = user_id.replace("id", "")
        return user_id
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"https://api.vk.com/method/groups.getById?group_id={user_id}&access_token={os.environ.get('API_KEY')}&v=5.154") as user:
                if user.status == 200:
                    user = await user.json()
                    user_id = user["response"][0]["id"]
        except KeyError:
            print("Ошибка получения группы. Проверьте правильность ссылки")
        except Exception as e:
            print(e)     
    return user_id
