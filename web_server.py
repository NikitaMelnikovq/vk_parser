from fastapi import FastAPI, Query, Request, Depends
from fastapi.responses import RedirectResponse
import httpx
from db.database import init_pool, close_pool
from db.connection_manager import get_db_connection

app = FastAPI()

CLIENT_ID = '51781233'
CLIENT_SECRET = 'Tme5VJdA5L5Cc5Z84x39'
REDIRECT_URI = 'http://localhost:8000/callback'
AUTH_URL = 'https://oauth.vk.com/authorize'
TOKEN_URL = 'https://oauth.vk.com/access_token'

@app.on_event("startup")
async def on_startup():
    await init_pool()

@app.on_event("shutdown")
async def on_shutdown():
    await close_pool()

@app.get('/')
async def read_root():
    return {"message": "Такой страницы не существует"}

@app.get('/login')
async def login(user_id: int = Query(...)):
    auth_url = f"{AUTH_URL}?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope=friends&response_type=code&state={user_id}"

    return RedirectResponse(auth_url)

@app.get('/callback')
async def callback(code: str, state: int):
    user_id = state
    async with httpx.AsyncClient() as client:
        token_response = await client.get(
            TOKEN_URL,
            params={
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET,
                'redirect_uri': REDIRECT_URI,
                'code': code
            }
        )
        
    token_data = token_response.json()
    access_token = token_data.get('access_token')

    if access_token:
        async with get_db_connection() as conn:
            async with conn.transaction(isolation="read_committed"):
                await conn.execute("""
        INSERT INTO users (api_key) 
        VALUES ($1)
        ON CONFLICT (user_id) 
        DO UPDATE SET api_key = EXCLUDED.api_key;
    """, access_token)
                await conn.execute("UPDATE users SET status='authorized' WHERE user_id=$1", user_id)
                await conn.execute("UPDATE users SET user_limit=3 WHERE user_id=$1", user_id)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)

         