import asyncio
import hashlib
import base64
import random
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import aiomysql
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

# ==============================
# Database configuration
# ==============================
MYSQL_CONFIG = {
    "host": "127.0.0.1",
    "port": 3307,
    "user": "apix",
    "password": "apixapix",
    "db": "apix_database",
    "autocommit": True,
}

# ==============================
# Symmetric encryption config
# ==============================
# NOTE:
# The key must be exactly the same as the one used on the client side.
# 16 / 24 / 32 bytes for AES-128 / 192 / 256
AES_KEY = b"0123456789abcdef"  # example key, replace in production
AES_IV = b"abcdef9876543210"   # example IV, replace in production

# ==============================
# FastAPI app
# ==============================
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    global mysql_pool
    # Create MySQL connection pool on startup
    mysql_pool = await aiomysql.create_pool(**MYSQL_CONFIG)
    try:
        yield
    finally:
        # Gracefully close MySQL pool on shutdown
        if mysql_pool:
            mysql_pool.close()
            await mysql_pool.wait_closed()


app = FastAPI(title="Auth Service", lifespan=lifespan)

mysql_pool: Optional[aiomysql.Pool] = None


# ==============================
# Models
# ==============================
class RegisterRequest(BaseModel):
    username: str
    password: str  # encrypted password from client


class LoginRequest(BaseModel):
    username: str
    password: str  # encrypted password from client


# ==============================
# Utility functions
# ==============================

def decrypt_password(encrypted_password: str) -> str:
    """
    Decrypt password from client using AES-CBC.
    The input is assumed to be base64 encoded.
    """
    try:
        cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
        encrypted_bytes = base64.b64decode(encrypted_password)
        decrypted = cipher.decrypt(encrypted_bytes)
        return unpad(decrypted, AES.block_size).decode("utf-8")
    except Exception:
        # Intentionally vague to avoid leaking crypto details
        raise HTTPException(status_code=400, detail="Invalid encrypted password")


def sha256_hash(raw_password: str) -> str:
    """
    Hash plaintext password using SHA256.
    """
    return hashlib.sha256(raw_password.encode("utf-8")).hexdigest()


# ==============================
# Startup / shutdown
# ==============================


# ==============================
# Routes
# ==============================
@app.post("/auth/register")
async def register(req: RegisterRequest):
    """
    Register a new user.

    Flow:
    1. Generate random 9-digit user_uid
    2. Decrypt password
    3. SHA256 hash
    4. Store into database
    5. Return generated user_uid
    """

    # Decrypt and hash password
    plain_password = decrypt_password(req.password)
    password_hash = sha256_hash(plain_password)

    try:
        async with mysql_pool.acquire() as conn:
            async with conn.cursor() as cur:

                # Try generating unique user_uid (rare collision, but handled)
                for _ in range(5):
                    # Generate 9-digit numeric UID
                    user_uid = str(random.randint(100_000_000, 999_999_999))

                    # Check uniqueness
                    await cur.execute(
                        "SELECT id FROM users WHERE user_uid=%s",
                        (user_uid,),
                    )
                    if not await cur.fetchone():
                        break
                else:
                    # Extremely unlikely unless database is cursed
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to generate unique user_uid"
                    )

                # Insert new user
                await cur.execute(
                    """
                    INSERT INTO users (user_uid, username, password)
                    VALUES (%s, %s, %s)
                    """,
                    (user_uid, req.username, password_hash),
                )

        return JSONResponse({
            "success": True,
            "messages": {
                "msg": "注册成功",
                "uid": user_uid
            },
        })
    except Exception as e:

        return JSONResponse({
            "success": False,
            "messages": {
                "msg": "注册失败: 重复的用户名",
                "uid": None
            },
        })



@app.post("/auth/login")
async def login(req: LoginRequest):
    """
    User login.

    Flow:
    1. Decrypt password
    2. SHA256 hash
    3. Compare with stored hash
    """
    plain_password = decrypt_password(req.password)
    password_hash = sha256_hash(plain_password)

    try:
        async with mysql_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    """
                    SELECT id, user_uid, username
                    FROM users
                    WHERE username=%s AND password=%s
                    """,
                    (req.username, password_hash),
                )
                user = await cur.fetchone()

        if not user:
            return JSONResponse({
                "success": False,
                "messages": {
                    "msg": "用户名与密码不匹配",
                    "uid": None
                },
            })
        return JSONResponse({
            "success": True,
            "messages": {
                    "msg": "登录成功",
                    "uid": user.get("user_uid")
                },
        })
    
    except Exception as e:

        return JSONResponse({
            "success": False,
            "messages": {
                "msg": "登录失败: 接口异常",
                "uid": None
            },
        })
    


# ==============================
# Local debug entry
# ==============================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
