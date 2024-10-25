import os
from gino import Gino
from dotenv import load_dotenv

load_dotenv()

db = Gino()

async def init_db():
    await db.set_bind(
        f'postgresql://postgres:{os.environ.get("PASSWORD")}@localhost:5432/{os.environ.get("DBNAME")}',
        min_size=1,
        max_size=20
    )

async def close_db():
    bind = db.pop_bind()
    if bind:
        await bind.close()