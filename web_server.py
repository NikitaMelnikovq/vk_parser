import os

import httpx
from fastapi import FastAPI, Query
from fastapi.responses import RedirectResponse
from cryptography.fernet import Fernet

from db.database import db, init_db, close_db

app = FastAPI()
encryption_key = os.getenv("ENCRYPTION_KEY")
cipher = Fernet(encryption_key.encode())

def encrypt_token(token: str) -> str:
    return cipher.encrypt(token.encode()).decode()

CLIENT_ID = os.environ.get('CLIENT_ID')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET')
REDIRECT_URI = 'http://localhost:8000/callback'
AUTH_URL = 'https://oauth.vk.com/authorize'
TOKEN_URL = 'https://oauth.vk.com/access_token'

@app.on_event("startup")
async def on_startup():
    await init_db()

@app.on_event("shutdown")
async def on_shutdown():
    await close_db()

@app.get('/')
async def read_root():
    return {"message": "Такой страницы не существует"}

@app.get('/login')
async def login(user_id: int = Query(...)):
    auth_url = f"{AUTH_URL}?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope=groups,wall,offline&response_type=code&state={user_id}"

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
        encrypted_token = encrypt_token(access_token)
        print(encrypted_token)
        async with db.transaction():
                await db.status("""
                    INSERT INTO users (user_id, api_key, status, user_limit)
                    VALUES ($1, $2, 'authorized', 3)
                    ON CONFLICT (user_id)
                    DO UPDATE
                    SET api_key = EXCLUDED.api_key,
                        status = CASE 
                                    WHEN users.status = 'authorized' THEN users.status
                                    ELSE EXCLUDED.status
                                END,
                        user_limit = CASE 
                                        WHEN users.status = 'authorized' THEN users.user_limit
                                        ELSE EXCLUDED.user_limit
                                    END;
                    """, user_id, encrypted_token)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)

         