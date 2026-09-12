import json
import sqlite3

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import settings
from app.services.quiz_service import load_questions
from app.services.rag_service import delete_question_from_index, index_question_by_id

router = APIRouter()
DB_PATH = settings.db_path

@router.get("/admin/questions")
def admin_get_questions():
    return JSONResponse(content=load_questions())

@router.post("/admin/add")
def admin_add_question(payload: dict):
    question = (payload.get("question") or "").strip()
    answer = (payload.get("answer") or "").strip().upper()
    options = payload.get("options")
    if not question:
        return JSONResponse(content={"error": "题干不能为空"}, status_code=400)
    if not options or not isinstance(options, dict) or len(options) < 2:
        return JSONResponse(content={"error": "选项至少要有 A、B 两项"}, status_code=400)
    if answer not in options:
        return JSONResponse(content={"error": "答案必须是选项里的一个（A/B/C/D）"}, status_code=400)
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT id FROM questions").fetchall()
    max_no = 0
    for r in rows:
        rid = str(r[0] or "")
        if rid.startswith("q") and rid[1:].isdigit():
            max_no = max(max_no, int(rid[1:]))
    new_id = "q" + str(max_no + 1).zfill(3)
    conn.execute(
        "INSERT INTO questions (id, course, chapter, knowledge_point, type, difficulty, question, options, answer, parsing, common_errors) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (new_id, payload.get("course") or "", payload.get("chapter") or "", payload.get("knowledge_point") or "",
         payload.get("type") or "单选题", payload.get("difficulty") or "中", question,
         json.dumps(options, ensure_ascii=False), answer, payload.get("parsing") or "", payload.get("common_errors") or ""),
    )
    conn.commit()
    conn.close()
    index_question_by_id(new_id)
    return JSONResponse(content={"ok": True, "id": new_id, "message": "已添加题目 " + new_id})

@router.post("/admin/update")
def admin_update_question(payload: dict):
    qid = (payload.get("id") or "").strip()
    if not qid:
        return JSONResponse(content={"error": "缺少题目 id"}, status_code=400)
    question = (payload.get("question") or "").strip()
    answer = (payload.get("answer") or "").strip().upper()
    options = payload.get("options")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    row = cur.execute("SELECT id FROM questions WHERE id=?", (qid,)).fetchone()
    if not row:
        conn.close()
        return JSONResponse(content={"error": "找不到题目 " + qid}, status_code=404)
    if options is not None and isinstance(options, dict):
        options_json = json.dumps(options, ensure_ascii=False)
    else:
        options_json = cur.execute("SELECT options FROM questions WHERE id=?", (qid,)).fetchone()[0]
    cur.execute(
        "UPDATE questions SET course=?, chapter=?, knowledge_point=?, type=?, difficulty=?, question=?, options=?, answer=?, parsing=?, common_errors=? WHERE id=?",
        (payload.get("course") or "", payload.get("chapter") or "", payload.get("knowledge_point") or "",
         payload.get("type") or "单选题", payload.get("difficulty") or "中", question, options_json, answer,
         payload.get("parsing") or "", payload.get("common_errors") or "", qid),
    )
    conn.commit()
    conn.close()
    index_question_by_id(qid)
    return JSONResponse(content={"ok": True, "message": "已更新题目 " + qid})

@router.post("/admin/delete")
def admin_delete_question(payload: dict):
    qid = (payload.get("id") or "").strip()
    if not qid:
        return JSONResponse(content={"error": "缺少题目 id"}, status_code=400)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM questions WHERE id=?", (qid,))
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    delete_question_from_index(qid)
    if deleted == 0:
        return JSONResponse(content={"error": "找不到题目 " + qid}, status_code=404)
    return JSONResponse(content={"ok": True, "message": "已删除题目 " + qid})
