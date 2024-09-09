from contextlib import asynccontextmanager
from db.database import get_connection, put_connection

@asynccontextmanager
async def get_db_connection():
    conn = await get_connection()
    try:
        yield conn
    finally:
        await put_connection(conn)
