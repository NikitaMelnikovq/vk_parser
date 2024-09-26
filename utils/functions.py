import aiohttp
import os
from db.connection_manager import get_db_connection
from datetime import datetime
from dotenv import load_dotenv
from logger.logger import setup_logger

load_dotenv()
logger = setup_logger()

VK_API_URL = "https://api.vk.com/method/groups.getById"
API_VERSION = "5.154"

async def fetch_group_data(session: aiohttp.ClientSession, group_id: str) -> dict:
    """Helper function to fetch group data from VK API."""
    url = f"{VK_API_URL}?group_id={group_id}&access_token={os.environ.get("API_KEY")}&v={API_VERSION}"
    try:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.json()
            else:
                print(f"Error: VK API request failed with status {response.status}")
                return None
    except Exception as e:
        print(f"Error fetching group data: {e}")
        return None


async def get_group_id(url: str) -> int:
    """Extract group ID from VK URL and fetch group information."""
    group_id = url.split("/")[-1]
    if group_id.startswith("club"):
        group_id = group_id.replace("club", "")
    
    async with aiohttp.ClientSession() as session:
        group_data = await fetch_group_data(session, group_id)
        if group_data:
            try:
                return group_data["response"][0]["id"]
            except (KeyError, IndexError) as e:
                print(f"Error in get_group_id - {e}")
                return -1
        else:
            return -1


async def get_group_name(group_id: int) -> str:
    async with aiohttp.ClientSession() as session:
        group_data = await fetch_group_data(session, str(group_id))
        if group_data:
            try:
                return group_data["response"]["groups"]["name"]
            
            except (KeyError, IndexError) as e:
                print(f"Error in get_group_name - {e}")
                print(group_data)
                return -1
        else:
            return -1

async def check_link(link: str) -> bool:
    group_id = link.split("/")[-1]
    if group_id.startswith("club"):
        group_id = group_id.replace("club", "")

    url = f"{VK_API_URL}?group_id={group_id}&access_token={os.environ.get('API_KEY')}&v=5.199"
    print(url)
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                print(data)
                return "response" in data
        except aiohttp.ClientError:
            
            return False

async def check_limit(user_id: int):
    async with get_db_connection() as conn, conn.transaction():
        subscribed = await conn.fetchval("SELECT subscribed FROM users WHERE user_id=$1", user_id)
        limit = 20 if subscribed else 3
        groups_count = await conn.fetchval("SELECT COUNT(*) FROM users_groups_rel WHERE user_id=$1", user_id)
        return groups_count < limit

async def add_group(user_id, link):
    group_id = await get_group_id(link)
    group_name = await get_group_name(group_id)
    async with get_db_connection() as conn, conn.transaction():
        try: 
            await conn.execute("""
                                    INSERT INTO user_groups (group_id, group_name)
                                    SELECT $1, $2::VARCHAR
                                    WHERE NOT EXISTS (
                                        SELECT 1 FROM user_groups WHERE group_id = $1 and group_name = $2
                                    );
                                """, group_id, group_name)
            await conn.execute("""
                                    INSERT INTO users_groups_rel (user_id, group_id, group_name)
                                    SELECT $1, $2, $3::VARCHAR
                                    WHERE NOT EXISTS (
                                        SELECT 1 FROM users_groups_rel WHERE user_id = $1 AND group_id = $2 AND group_name = $3
                                    );
                                """, user_id, group_id, group_name)
            return 1
        except Exception as e:
            print(e)
            return 0
            
async def remove_group(user_id, link):
    group_id = await get_group_id(link)

    async with get_db_connection() as conn, conn.transaction():
        try:
            await conn.execute("DELETE FROM users_groups_rel WHERE user_id=$1 AND group_id=$2", user_id, group_id)
            return 1
        except Exception as e:
            print(e)
            return 0
        
async def get_group_count():
    async with get_db_connection() as conn, conn.transaction():
        try:
            result = await conn.fetchval('SELECT COUNT(*) FROM your_table')
            return result
        except Exception as e:
            print(e)
            print("Exception occured in file functions.py in get_group_count function")
            return -1

async def get_api_keys():
    async with get_db_connection() as conn, conn.transaction():  
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
            
async def get_group_list(user_id):
    async with get_db_connection() as conn, conn.transaction():
        try:
            groups = await conn.fetch("SELECT group_name FROM users_groups_rel WHERE user_id=$1", user_id)
            groups = [row['group_name'] for row in groups]
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
