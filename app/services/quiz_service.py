# 公共工具箱：被多个路由共用的业务函数都放这里，避免"互相找对方"卡死
import json
import sqlite3
from datetime import datetime, timedelta

from app.config import settings

# AI 临时题的内存库（不写进数据库）：generate-similar 出的题放这，check/records/wrong 都能判
gen_bank = []


# 考点权重 → 系数（越小 → 间隔越短 → 复习越勤）
WEIGHT_FACTOR = {"核心": 0.7, "普通": 1.0, "边缘": 1.5}

# 知识类型 → 系数
TYPE_FACTOR = {"记忆": 1.0, "概念": 1.0, "流程": 0.8, "设计": 1.2}


def sm2(ef, interval, reps, q, weight="普通", ktype="概念"):
    """q=回忆质量 0-5（>=3 算答对）。weight=考点权重，ktype=知识类型。
    返回 (新ef, 新interval, 新reps)。"""
    if q < 3:
        reps = 0
        interval = 1                      # 答错：明天重来
    else:
        if reps == 0:
            interval = 1
        elif reps == 1:
            interval = 6
        else:
            interval = round(interval * ef)
        reps += 1

        # 新增：按「考点权重」和「知识类型」调整间隔
        interval = interval * WEIGHT_FACTOR.get(weight, 1.0)
        interval = interval * TYPE_FACTOR.get(ktype, 1.0)

    ef = ef + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))   # 难度因子更新公式
    if ef < 1.3:
        ef = 1.3                          # EF 下限

    # 新增：边界
    interval = round(interval)
    interval = max(interval, 1)
    interval = min(interval, 60)

    return ef, interval, reps



def srs_update(uid, qid, correct):
    """按 SM-2 更新某用户某题的复习状态（correct=True→记得 q=5，False→忘了 q=2）"""
    if not uid or not qid:
        return
    q = 5 if correct else 2
    now = datetime.now()
    conn = sqlite3.connect(settings.db_path); conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM srs WHERE user_id=? AND qid=?", (uid, qid)).fetchone()
    ef, interval, reps = (row["ef"], row["interval"], row["reps"]) if row else (2.5, 0, 0)

    # 查出这道题的「考点权重」和「知识类型」
    qrow = conn.execute(
        "SELECT weight, knowledge_type FROM questions WHERE id=?", (qid,)
    ).fetchone()
    weight = (qrow["weight"] if qrow else "") or "普通"
    ktype = (qrow["knowledge_type"] if qrow else "") or "概念"

    ef, interval, reps = sm2(ef, interval, reps, q, weight, ktype)
    due = (now + timedelta(days=int(interval))).isoformat(timespec="seconds")
    conn.execute(
        """INSERT INTO srs (user_id, qid, ef, interval, reps, due, last, created_at)
           VALUES (?,?,?,?,?,?,?,?)
           ON CONFLICT(user_id, qid) DO UPDATE SET
             ef=excluded.ef, interval=excluded.interval, reps=excluded.reps,
             due=excluded.due, last=excluded.last""",
        (uid, qid, ef, interval, reps, due, now.isoformat(timespec="seconds"), now.isoformat(timespec="seconds"))
    )
    conn.commit(); conn.close()


def load_questions(course: str = "", chapter: str = ""):
    conn = sqlite3.connect(settings.db_path)          # 连数据库
    conn.row_factory = sqlite3.Row           # 行能用列名取值（像字典）
    sql = "SELECT * FROM questions WHERE 1=1"
    args = []
    if course:
        sql += " AND course=?"; args.append(course)
    if chapter:
        sql += " AND chapter=?"; args.append(chapter)
    rows = conn.execute(sql, args).fetchall()
    conn.close()                             # 用完关连接
    questions = []
    for r in rows:
        questions.append({
            "id": r["id"],
            "course": r["course"],
            "chapter": r["chapter"],
            "knowledge_point": r["knowledge_point"],
            "type": r["type"],
            "difficulty": r["difficulty"],
            "question": r["question"],
            "options": json.loads(r["options"]) if r["options"] else {},  # 字符串拆回字典
            "answer": r["answer"],
            "parsing": r["parsing"],
            "common_errors": r["common_errors"],
            "weight": r["weight"] or "普通",
            "knowledge_type": r["knowledge_type"] or "概念",
        })

    return questions


def load_records():
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM records ORDER BY id").fetchall()
    conn.close()
    records = []
    for r in rows:
        records.append({
            "ts": r["ts"],
            "question_id": r["question_id"],
            "index": r["idx"],
            "knowledge_point": r["knowledge_point"],
            "correct": bool(r["correct"]),
            "your_answer": r["your_answer"],
            "answer": r["answer"],
            "user_id": r["user_id"],
        })
    return records


def save_records(records):
    conn = sqlite3.connect(settings.db_path)
    cur = conn.cursor()
    cur.execute("DELETE FROM records")            # 清空旧数据
    for rec in records:
        cur.execute(
            "INSERT INTO records (ts, question_id, idx, knowledge_point, correct, your_answer, answer, user_id) VALUES (?,?,?,?,?,?,?,?)",
            (
                rec.get("ts"),
                rec.get("question_id"),
                rec.get("index"),
                rec.get("knowledge_point"),
                1 if rec.get("correct") else 0,
                rec.get("your_answer"),
                rec.get("answer"),
                rec.get("user_id"),
            ),
        )
    conn.commit()                                 # 提交才真正写入
    conn.close()
