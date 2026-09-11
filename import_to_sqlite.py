# 印库 JSON -> SQLite 一次性导入脚本
# 运行位置：印库根目录（和 app、data 平级）
# 运行命令：venv\Scripts\python.exe import_to_sqlite.py
import json
import os
import sqlite3

BASE = r"C:\Users\36085\Desktop\印库\data"          # data 目录
DB_PATH = os.path.join(BASE, "yinku.db")             # 数据库文件

# 1) 连接数据库（文件不存在会自动创建，不用手动建）
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# 2) 建表：IF NOT EXISTS = 已经建过就不会重复建（脚本可安全重跑）
cur.execute("""
CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY,          -- 题号
    course TEXT,                  -- 课程
    chapter TEXT,                 -- 章节（第1章…第8章）
    knowledge_point TEXT,         -- 知识点
    type TEXT,                    -- 题型
    difficulty TEXT,              -- 难度
    question TEXT,                -- 题干
    options TEXT,                 -- 选项（字典，下面转成 JSON 字符串存）
    answer TEXT,                  -- 答案
    parsing TEXT,                 -- 解析
    common_errors TEXT            -- 常见错误
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 自增序号
    ts TEXT,                      -- 作答时间
    question_id TEXT,             -- 哪道题
    idx INTEGER,                  -- 题号下标（index 是 SQL 关键字，改名 idx）
    knowledge_point TEXT,         -- 知识点
    correct INTEGER,              -- 对错（True/False 存成 1/0）
    your_answer TEXT,             -- 你答的
    answer TEXT                   -- 正确答案
)
""")

# 3) 读旧 JSON（records 可能不存在/为空，兜底成空列表）
with open(os.path.join(BASE, "questions.json"), "r", encoding="utf-8") as f:
    questions = json.load(f)
try:
    with open(os.path.join(BASE, "records.json"), "r", encoding="utf-8") as f:
        records = json.load(f)
except Exception:
    records = []

# 4) 灌题目：SQLite 存不了"字典"，所以 options 先转成 JSON 字符串
for q in questions:
    cur.execute(
        "INSERT OR REPLACE INTO questions (id, course, chapter, knowledge_point, type, difficulty, question, options, answer, parsing, common_errors) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            q.get("id"), q.get("course"), q.get("chapter"), q.get("knowledge_point"),
            q.get("type"), q.get("difficulty"), q.get("question"),
            json.dumps(q.get("options", {}), ensure_ascii=False),
            q.get("answer"), q.get("parsing"), q.get("common_errors"),
        ),
    )

# 5) 灌记录：SQLite 没有布尔值，True 存 1、False 存 0
for r in records:
    cur.execute(
        "INSERT INTO records (ts, question_id, idx, knowledge_point, correct, your_answer, answer) VALUES (?,?,?,?,?,?,?)",
        (
            r.get("ts"), r.get("question_id"), r.get("index"),
            r.get("knowledge_point"), 1 if r.get("correct") else 0,
            r.get("your_answer"), r.get("answer"),
        ),
    )

conn.commit()                                        # 提交，数据才真正写入
print(f"导入完成：{len(questions)} 道题，{len(records)} 条记录")
conn.close()
