import asyncio

from db.database import db, init_db, close_db


async def main():
    await init_db()
    async with db.transaction():
        result = await db.first("""SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'api_key';""")
        print(result)
    await close_db()


if __name__ == "__main__":
    asyncio.run(main())