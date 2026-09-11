from fastapi import APIRouter
from fastapi.responses import JSONResponse
import sqlite3
from app.config import settings

router = APIRouter()

@router.get("/courses")
def get_courses():
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT DISTINCT course FROM questions WHERE course <> ''").fetchall()
    conn.close()
    return JSONResponse(content=[r["course"] for r in rows])
