# 印库 v1 第二格：FastAPI 读 cards.json，支持按分类筛选
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import json
import os
import re
import httpx
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
import chromadb
from app.config import settings
from app.logging_config import setup_logging
from app.errors import register_exception_handlers
from app.api.routers.practice import router as practice_router
from app.services.quiz_service import gen_bank, load_questions, srs_update, load_records, save_records
from app.api.routers.review import router as review_router
from app.api.routers.courses import router as courses_router
from app.api.routers.records import router as records_router
from app.api.routers.profile import router as profile_router
from app.api.routers.ai import router as ai_router
from app.api.routers.admin import router as admin_router
from app.api.routers.learn import router as learn_router
from app.api.routers.rag import router as rag_router
from app.api.routers.auth import router as auth_router




# ===== 路径配置：全部相对项目根目录，换机器也能跑 =====
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # app/main.py 的上一级 = 印库根目录
DATA_DIR = os.path.join(BASE_DIR, "data")
CARDS_PATH = os.path.join(DATA_DIR, "cards.json")


app = FastAPI(title="印库 v1 API", version="0.7.0")
setup_logging()
register_exception_handlers(app)
app.include_router(practice_router)
app.include_router(review_router)
app.include_router(courses_router)
app.include_router(profile_router)
app.include_router(ai_router)
app.include_router(records_router)
app.include_router(admin_router)
app.include_router(learn_router)
app.include_router(rag_router)
app.include_router(auth_router)


# 允许前端网页跨域调用此 API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # * = 任何来源都允许（开发阶段够用）
    allow_credentials=True,
    allow_methods=["*"],       # 允许所有 HTTP 方法（GET/POST 等）
    allow_headers=["*"],       # 允许所有请求头
)

# ============================================================
# 以题代练：题库 + 判题（第一阶段）
# ============================================================

DB_PATH = settings.db_path  # 改从配置层读取，值不变，仍是 data/yinku.db

# ===== 用户档案表：支持"书架→点书→弹窗建档→AI诊断"流程（step two） =====
def init_db():
    """启动时确保 profiles 表存在；questions/records 由导入脚本建，这里只补档案表。"""
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
    user_id       TEXT PRIMARY KEY,
    username      TEXT UNIQUE,
    password_hash TEXT,
    salt          TEXT,
    created_at    TEXT
)""")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS profiles (
        user_id      TEXT PRIMARY KEY,   -- 用户标识（先用设备id，接小程序再换 openid）
        school       TEXT,               -- 学校
        major        TEXT,               -- 专业
        course       TEXT,               -- 当前在学课程（对应书架上的一本书）
        level        TEXT,               -- 自报水平：小白/期末复习/考研/保研...
        expectation  TEXT,               -- 其他期望：目标分、薄弱点、节奏等
        created_at   TEXT,
        updated_at   TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS srs (
        user_id     TEXT,
        qid         TEXT,                -- 题号（如 q214）
        ef          REAL DEFAULT 2.5,   -- 难度因子（SM-2）
        interval    REAL DEFAULT 0,     -- 下次间隔（天）
        reps        INT  DEFAULT 0,     -- 连续答对次数
        due         TEXT DEFAULT '',    -- 下次复习日期 ISO
        last        TEXT DEFAULT '',    -- 上次复习日期
        created_at  TEXT,
        PRIMARY KEY (user_id, qid)
    )""")
    conn.commit()
    conn.close()