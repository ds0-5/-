# 刷题 & 判题路由：只管"接请求、回结果"，活儿都调 quiz_service 里的函数
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services.quiz_service import gen_bank, load_questions, srs_update

router = APIRouter()

# 取题接口：返回题目列表，但【故意不含答案/解析/常见错误】
@router.get("/questions")
def get_questions(course: str = "", chapter: str = ""):
    questions = load_questions(course=course, chapter=chapter)
    safe = []
    for q in questions:
        safe.append({
            "id": q.get("id"),
            "course": q.get("course"),
            "chapter": q.get("chapter"),
            "knowledge_point": q.get("knowledge_point"),
            "type": q.get("type"),
            "difficulty": q.get("difficulty"),
            "question": q.get("question"),
            "options": q.get("options"),
            "weight": q.get("weight") or "普通",
            "knowledge_type": q.get("knowledge_type") or "概念",
        })
    return JSONResponse(content=safe)

# 判题接口
@router.post("/check")
def check_answer(payload: dict):
    chapter = payload.get("chapter") or ""      # 章节筛选：保证下标和 /questions 对齐
    questions = load_questions(chapter=chapter) + gen_bank    # gen_bank：AI 临时出的题也能判
    idx = payload.get("index")                    # 第几题（从 0 开始）
    user_ans = (payload.get("answer") or "").strip().upper()   # 用户答案，去空格+转大写（B 和 b 都算对）
    if not isinstance(idx, int) or not (0 <= idx < len(questions)):
        return JSONResponse(content={"error": "题目索引无效"}, status_code=400)
    q = questions[idx]
    correct_ans = (q.get("answer") or "").strip().upper()      # 标准答案也统一大写再比
    uid = payload.get("user_id") or ""
    if uid:
        srs_update(uid, q.get("id"), user_ans == correct_ans)
    return JSONResponse(content={
        "correct": user_ans == correct_ans,
        "your_answer": user_ans,
        "answer": q.get("answer", ""),
        "parsing": q.get("parsing", ""),
        "common_errors": q.get("common_errors", ""),
    })
