import asyncio 

from utils.functions import convert_time, get_group_time
from db.database import close_db, init_db

async def main():
    await init_db()
    result = await get_group_time(227736130)
    print(result > 1000)
    await close_db()

if __name__ == "__main__":
    asyncio.run(main())