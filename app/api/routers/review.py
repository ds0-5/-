# 复习路由：今日复习队列 + 显式自评，活儿调 quiz_service 里的 srs_update
import json
import sqlite3
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.config import settings
from app.security import current_user
from app.services.quiz_service import srs_update

router = APIRouter()


# 显式自评（复习页用）：前端说这题答对/答错，后端更新复习排期
@router.post("/review")
def review(payload: dict, uid: str = Depends(current_user)):
    qid = (payload.get("qid") or "").strip()
    if not qid:
        return JSONResponse(content={"error": "缺少 qid"}, status_code=400)
    srs_update(uid, qid, bool(payload.get("correct", True)))
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM srs WHERE user_id=? AND qid=?", (uid, qid)).fetchone()
    conn.close()
    return JSONResponse(
        content={
            "ok": True,
            "qid": qid,
            "next_interval_days": int(row["interval"]),
            "next_due": row["due"],
            "ef": round(row["ef"], 2),
        }
    )


# 取今天该复习的题（复习队列）
@router.get("/due")
def due_cards(
    user_id: str = Depends(current_user),
    course: str = "",
    chapter: str = "",
    limit: int = 50,
    include_new: bool = False,
):
    today = datetime.now().isoformat(timespec="seconds")
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    base = (
        "SELECT s.qid AS qid, s.due AS due, s.interval AS interval, s.reps AS reps, "
        "q.question, q.options, q.answer, q.chapter, q.knowledge_point, q.type "
        "FROM srs s JOIN questions q ON q.id=s.qid WHERE s.user_id=? AND s.due<>'' AND s.due<=?"
    )
    args = [user_id, today]
    if course:
        base += " AND q.course=?"
        args.append(course)
    if chapter:
        base += " AND q.chapter=?"
        args.append(chapter)
    if include_new:
        new = (
            "SELECT q.id AS qid, '' AS due, 0 AS interval, 0 AS reps, "
            "q.question, q.options, q.answer, q.chapter, q.knowledge_point, q.type "
            "FROM questions q WHERE q.type NOT IN ('fill','apply','comprehensive') "
            "AND q.id NOT IN (SELECT qid FROM srs WHERE user_id=?)"
        )
        nargs = [user_id]
        if course:
            new += " AND q.course=?"
            nargs.append(course)
        if chapter:
            new += " AND q.chapter=?"
            nargs.append(chapter)
        base = base + " UNION " + new
        args = args + nargs
    base += " ORDER BY due ASC LIMIT ?"
    args.append(limit)
    rows = conn.execute(base, args).fetchall()
    conn.close()
    out = []
    for r in rows:
        out.append(
            {
                "qid": r["qid"],
                "due": r["due"],
                "interval": r["interval"],
                "reps": r["reps"],
                "question": r["question"],
                "options": json.loads(r["options"]) if r["options"] else {},
                "answer": r["answer"],
                "chapter": r["chapter"],
                "knowledge_point": r["knowledge_point"],
                "type": r["type"],
            }
        )
    return JSONResponse(content=out)
