from fastapi import APIRouter
from fastapi.responses import JSONResponse
import sqlite3
from app.config import settings

router = APIRouter()
DB_PATH = settings.db_path

@router.get("/learn/questions")
def learn_questions():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM questions WHERE type IN ('fill','apply','comprehensive') ORDER BY id").fetchall()
    conn.close()
    result = []
    for r in rows:
        result.append({
            "id": r["id"], "course": r["course"], "chapter": r["chapter"],
            "knowledge_point": r["knowledge_point"], "type": r["type"], "difficulty": r["difficulty"],
            "question": r["question"], "answer": r["answer"], "parsing": r["parsing"],
        })
    return JSONResponse(content={"total": len(result), "questions": result})
