import hashlib
import os
import sqlite3
import uuid
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import settings

router = APIRouter()

def _hash_password(password: str, salt_hex: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 100000).hex()

def _ensure_users_table():
    conn = sqlite3.connect(settings.db_path)
    conn.execute("CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT, salt TEXT, created_at TEXT)")
    conn.commit()
    conn.close()

_ensure_users_table()


@router.post("/auth/register")
def register(payload: dict):
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    if not username or not password:
        return JSONResponse(content={"error": "用户名和密码必填"}, status_code=400)
    conn = sqlite3.connect(settings.db_path); conn.row_factory = sqlite3.Row
    _ensure_users_table()
    if conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
        conn.close()
        return JSONResponse(content={"error": "用户名已存在"}, status_code=409)
    salt = os.urandom(16).hex()
    password_hash = _hash_password(password, salt)
    user_id = "u_" + uuid.uuid4().hex[:12]
    conn.execute("INSERT INTO users (user_id, username, password_hash, salt, created_at) VALUES (?,?,?,?,?)",
                 (user_id, username, password_hash, salt, datetime.now().isoformat(timespec="seconds")))
    conn.commit(); conn.close()
    return JSONResponse(content={"user_id": user_id, "username": username})

@router.post("/auth/login")
def login(payload: dict):
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    conn = sqlite3.connect(settings.db_path); conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    if not row or _hash_password(password, row["salt"]) != row["password_hash"]:
        return JSONResponse(content={"error": "用户名或密码错误"}, status_code=401)
    return JSONResponse(content={"user_id": row["user_id"], "username": row["username"]})
