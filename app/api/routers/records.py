from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services.quiz_service import gen_bank, load_questions, load_records, save_records

router = APIRouter()

# 记录一次练习：前端把"第几题+答案"发来，后端自己判题、自己落库
# 为什么后端再判一次：不信任前端报的"对错"，防止有人篡改记录数据
@router.post("/records")
def add_record(payload: dict):
    chapter = payload.get("chapter") or ""      # 章节筛选：下标与 /questions 对齐，避免记错题
    questions = load_questions(chapter=chapter) + gen_bank    # gen_bank：AI 临时题也记录
    idx = payload.get("index")
    user_ans = (payload.get("answer") or "").strip().upper()
    if idx is None or not (0 <= idx < len(questions)):
        return JSONResponse(content={"error": "题目索引无效"}, status_code=400)
    q = questions[idx]
    correct = user_ans == (q.get("answer") or "").strip().upper()   # 后端自己判对错
    records = load_records()
    record = {
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),   # 作答时间
        "question_id": q.get("id"),          # 哪道题
        "index": idx,
        "knowledge_point": q.get("knowledge_point", ""),   # 哪个知识点（后面按它聚合薄弱项）
        "correct": correct,                  # 对错
        "your_answer": user_ans,             # 你答了什么
        "answer": q.get("answer", ""),       # 正确答案
        "user_id": payload.get("user_id") or "",   # 谁答的
    }
    records.append(record)
    save_records(records)
    return JSONResponse(content={"ok": True, "record": record})

# 薄弱知识点：翻 records，按知识点聚合算错误率，最薄弱的排最前
@router.get("/stats/weakpoints")
def weakpoints(user_id: str = ""):
    records = load_records()
    if not records:
        return JSONResponse(content={"total_records": 0, "weakpoints": []})
    agg = {}
    for r in records:
        if user_id and (r.get("user_id") or "") != user_id:
            continue                        # 不是这个人的，跳过
        kp = r.get("knowledge_point") or "未知知识点"
        if kp not in agg:
            agg[kp] = {"total": 0, "correct": 0, "wrong": 0}
        agg[kp]["total"] += 1
        if r.get("correct"):
            agg[kp]["correct"] += 1
        else:
            agg[kp]["wrong"] += 1
    result = []
    for kp, v in agg.items():
        result.append({
            "knowledge_point": kp,
            "total": v["total"],
            "correct": v["correct"],
            "wrong": v["wrong"],
            "wrong_rate": round(v["wrong"] / v["total"] * 100, 1),   # 错误率 = 错题数 ÷ 总答题数
        })
    result.sort(key=lambda x: x["wrong_rate"], reverse=True)   # 最薄弱的排最前
    return JSONResponse(content={"total_records": len(records), "weakpoints": result})

# 按薄弱知识点推荐下一题
@router.get("/recommend")
def recommend():
    questions = load_questions()
    records = load_records()
    if not questions:
        return JSONResponse(content={"error": "题库为空"}, status_code=400)

    # 每个知识点的答题统计：total 答了几次、correct 对了几次
    kp_stat = {}
    for r in records:
        kp = r.get("knowledge_point") or "未知"
        if kp not in kp_stat:
            kp_stat[kp] = {"total": 0, "correct": 0}
        kp_stat[kp]["total"] += 1
        if r.get("correct"):
            kp_stat[kp]["correct"] += 1

    # 被答对过的题 = 掌握题（不再优先推）
    mastered_qids = {r.get("question_id") for r in records if r.get("correct")}

    # 算一个知识点的"薄弱度"：错误率越高越薄弱；没练过的给 0.5 兜底（值得练）
    def kp_weakness(kp):
        s = kp_stat.get(kp)
        if not s or s["total"] == 0:
            return 0.5
        return 1.0 - s["correct"] / s["total"]

    # 候选 = 还没答对过的题；全答对过就全部重推（当复习）
    candidates = [i for i, q in enumerate(questions) if q.get("id") not in mastered_qids]
    if not candidates:
        candidates = list(range(len(questions)))

    # 在候选里选薄弱知识点最强的题
    candidates.sort(key=lambda i: kp_weakness(questions[i].get("knowledge_point") or ""), reverse=True)
    pick = candidates[0]
    q = questions[pick]
    return JSONResponse(content={
        "index": pick,
        "reason": f"你「{q.get('knowledge_point')}」这块最薄弱，先练它",
        "id": q.get("id"),
        "course": q.get("course"),
        "chapter": q.get("chapter"),
        "knowledge_point": q.get("knowledge_point"),
        "type": q.get("type"),
        "difficulty": q.get("difficulty"),
        "question": q.get("question"),
        "options": q.get("options"),
    })


# 错题本：把答错过的题挑出来，统计每题错了几次
@router.get("/wrong")
def wrong_questions(user_id: str = ""):
    questions = load_questions()      # 题库：拿题干、选项、解析
    records = load_records()          # 答题卡：拿对错、题号

    # 第一步：数一数每道题错了几次
    wrong_count = {}
    for r in records:
        if r.get("correct"):
            continue                        # 答对的不算
        if user_id and (r.get("user_id") or "") != user_id:
            continue                        # 不是这个人的，跳过
        qid = r.get("question_id")
        wrong_count[qid] = wrong_count.get(qid, 0) + 1

    # 第二步：拿题号去题库，把题目换出来
    result = []
    for q in questions:
        if q.get("id") in wrong_count:        # 这道题在错题名单里
            result.append({
                "question": q.get("question"),
                "options": q.get("options"),
                "answer": q.get("answer"),
                "wrong_times": wrong_count[q.get("id")],
                "knowledge_point": q.get("knowledge_point"),
                "parsing": q.get("parsing"),
                "common_errors": q.get("common_errors"),
            })

    return JSONResponse(content={"wrong_questions": result})
