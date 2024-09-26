import os
from dotenv import load_dotenv
import asyncpg

load_dotenv()

class ConnectionPool:
    def __init__(self):
        self.pool = None

    async def init(self):
        self.pool = await asyncpg.create_pool(
            min_size=1,
            max_size=100,
            user='postgres',
            password=os.environ.get("PASSWORD"),
            database=os.environ.get("DBNAME"),
            host="localhost",
            port=5432
        )

    async def close(self):
        await self.pool.close()

    async def get_connection(self):
        return await self.pool.acquire()
    async def put_connection(self, conn):
        await self.pool.release(conn)

connection_pool = ConnectionPool()

async def get_connection():
    return await connection_pool.get_connection()

async def put_connection(conn):
    await connection_pool.put_connection(conn)

async def init_pool():
    await connection_pool.init()

async def close_pool():
    await connection_pool.close()
