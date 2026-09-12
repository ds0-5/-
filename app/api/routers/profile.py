import sqlite3
from datetime import datetime

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import settings

router = APIRouter()

# 建档/更新档案：user_id 唯一，重复建档就更新
@router.post("/profile")
def save_profile(payload: dict):
    uid = (payload.get("user_id") or "").strip()
    if not uid:
        return JSONResponse(content={"error": "缺少 user_id"}, status_code=400)
    now = datetime.now().isoformat(timespec="seconds")
    conn = sqlite3.connect(settings.db_path)
    conn.execute(
        """INSERT INTO profiles (user_id, school, major, course, level, expectation, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?)
           ON CONFLICT(user_id) DO UPDATE SET
             school=excluded.school, major=excluded.major, course=excluded.course,
             level=excluded.level, expectation=excluded.expectation, updated_at=excluded.updated_at""",
        (uid, payload.get("school", ""), payload.get("major", ""), payload.get("course", ""),
         payload.get("level", ""), payload.get("expectation", ""), now, now),
    )
    conn.commit()
    conn.close()
    return JSONResponse(content={"ok": True, "user_id": uid})


@router.get("/profile")
def get_profile(user_id: str = ""):
    if not user_id:
        return JSONResponse(content={"error": "缺少 user_id"}, status_code=400)
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    r = conn.execute("SELECT * FROM profiles WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    if not r:
        return JSONResponse(content={"error": "无档案"}, status_code=404)
    return JSONResponse(content=dict(r))


# AI 诊断 + 学习路径：弹窗点"生成方案"时调用，需要用户已建档
@router.post("/diagnose")
def diagnose(payload: dict):
    uid = (payload.get("user_id") or "").strip()
    if not uid:
        return JSONResponse(content={"error": "缺少 user_id"}, status_code=400)
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    prof = conn.execute("SELECT * FROM profiles WHERE user_id=?", (uid,)).fetchone()
    if not prof:
        conn.close()
        return JSONResponse(content={"error": "请先建档"}, status_code=400)
    course = prof["course"] or ""
    rows = conn.execute(
        "SELECT DISTINCT chapter, knowledge_point FROM questions WHERE course=? AND chapter<>'' ORDER BY chapter",
        (course,),
    ).fetchall()
    conn.close()
    chapters = [{"chapter": r["chapter"], "knowledge_point": r["knowledge_point"]} for r in rows]
    profile_text = (
        f"学校：{prof['school']}；专业：{prof['major']}；课程：{course}；"
        f"自报水平：{prof['level']}；期望：{prof['expectation']}"
    )
    chapter_text = "\n".join(f"{i+1}. {c['chapter']}（{c['knowledge_point']}）" for i, c in enumerate(chapters))
    instruction = (
        "你是「印库」的学习规划师，负责给学生做诊断并给出个性化学习路径。\n"
        "\n【学生档案】\n" + profile_text + "\n"
        "\n【已学章节结构（先修顺序）】\n" + chapter_text + "\n"
        "\n请基于以上信息输出：\n"
        "① 当前水平诊断（对照他的自报水平，判断是相符还是夸大/低估）\n"
        "② 薄弱点分析（结合章节结构，说明他容易卡在哪）\n"
        "③ 分阶段学习路径（按章节先修顺序排，标清先后、别跳步）\n"
        "④ 每日/每周节奏建议（具体到每天练多久、练哪块）\n"
        "口吻：口语、大白话，别堆术语，戳中要害就停。"
    )
    ollama_url = "http://127.0.0.1:11434/api/generate"
    try:
        resp = httpx.post(
            ollama_url,
            json={"model": "qwen2.5:7b", "prompt": instruction, "stream": False},
            timeout=120,
        )
        data = resp.json()
        return JSONResponse(content={"user_id": uid, "plan": data.get("response", "")})
    except Exception as e:
        return JSONResponse(content={"error": "调用 Ollama 失败：" + str(e)}, status_code=500)
