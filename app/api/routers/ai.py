import json
import os
import re

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import BASE_DIR
from app.services.quiz_service import gen_bank, load_questions
from app.services.rag_service import hybrid_search

router = APIRouter()

# 老师考点卡片目录（data 下你复制进来的 8 个 md 文件）
DATA_DIR = str(BASE_DIR / "data")
KNOWLEDGE_DIR = os.path.join(DATA_DIR, "suanfa_考点卡片")


# 读某一章的笔记全文：题目 chapter 是"第3章"，就找"第3章_xxx.md"读回来
def load_knowledge_chapter(chapter):
    if not chapter:
        return ""
    try:
        files = os.listdir(KNOWLEDGE_DIR)
    except Exception:
        return ""
    for fn in files:
        if fn.startswith(chapter) and fn.endswith(".md"):
            try:
                with open(os.path.join(KNOWLEDGE_DIR, fn), "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                return ""
    return ""


# 以某道题当模板，让 Ollama 生成一道"同知识点、不同数字/情境"的选择题
@router.post("/generate-similar")
def generate_similar(payload: dict):
    chapter = payload.get("chapter") or ""  # 章节筛选：出的相似题属于同一章
    questions = load_questions(chapter=chapter)
    idx = payload.get("index")
    if idx is None or not (0 <= idx < len(questions)):
        return JSONResponse(content={"error": "题目索引无效"}, status_code=400)
    sample = questions[idx]

    prompt = (
        "你是「印库」的出题老师。请参考下面这道题，出一道【同知识点、同题型、题干结构和它相似但数字/情境不同】的新选择题。\n"
        f"【参考题】{sample.get('question', '')}\n"
        f"【选项】{sample.get('options', '')}\n"
        f"【知识点】{sample.get('knowledge_point', '')}\n\n"
        "只输出一个 JSON，不要任何多余文字，格式：\n"
        '{"question": "题干", "options": {"A": "选项A", "B": "选项B", "C": "选项C", "D": "选项D"}, "answer": "正确项字母", "parsing": "解析", "common_errors": "常见错误"}\n'
        "要求：答案必须唯一且正确；解析要讲清思路。"
    )
    ollama_url = "http://127.0.0.1:11434/api/generate"
    try:
        resp = httpx.post(
            ollama_url, json={"model": "qwen2.5:7b", "prompt": prompt, "stream": False}, timeout=120
        )
        text = resp.json().get("response", "")
    except Exception as e:
        return JSONResponse(content={"error": "调用 Ollama 失败：" + str(e)}, status_code=500)

    # 从模型回复里抠出第一个 { ... }（模型偶尔会带点废话，用正则兜底）
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return JSONResponse(content={"error": "模型没返回 JSON，再试一次"}, status_code=500)
    try:
        g = json.loads(m.group(0))
    except Exception:
        return JSONResponse(
            content={"error": "模型返回的 JSON 解析失败，再试一次"}, status_code=500
        )

    new_q = {
        "id": f"gen-{len(gen_bank) + 1}",  # AI 题唯一 id（gen- 开头，与正式题区分）
        "course": sample.get("course", ""),  # 沿用参考题的课程/章节/知识点
        "chapter": sample.get("chapter", ""),
        "knowledge_point": sample.get("knowledge_point", ""),
        "type": "choice",
        "difficulty": sample.get("difficulty", "medium"),
        "question": g.get("question", ""),
        "options": g.get("options", {}),
        "answer": (g.get("answer") or "").strip().upper(),
        "parsing": g.get("parsing", ""),
        "common_errors": g.get("common_errors", ""),
        "source": "AI 生成（临时，重启消失）",
        "review_status": "ai",
    }
    gen_bank.append(new_q)

    # 返回"安全字段"给前端（不含答案/解析），index = 正式题数 + 临时题数 - 1
    return JSONResponse(
        content={
            "index": len(questions) + len(gen_bank) - 1,
            "question": {
                "id": new_q["id"],
                "course": new_q["course"],
                "chapter": new_q["chapter"],
                "knowledge_point": new_q["knowledge_point"],
                "type": new_q["type"],
                "difficulty": new_q["difficulty"],
                "question": new_q["question"],
                "options": new_q["options"],
            },
        }
    )


# AI 讲解：答完一题后，让本地 Ollama 用大白话讲一遍：考什么、错在哪、怎么想
# 独立接口的原因：判题 /check 要秒回，不能等模型慢慢转；AI 讲解是"增值"，慢点无所谓
@router.post("/explain")
def ai_explain(payload: dict):
    chapter = payload.get("chapter") or ""  # 章节筛选：讲解的题和练习的是同一章
    questions = load_questions(chapter=chapter) + gen_bank  # gen_bank：AI 临时出的题也能讲解
    idx = payload.get("index")
    user_ans = (payload.get("answer") or "").strip().upper()
    if idx is None or not (0 <= idx < len(questions)):
        return JSONResponse(content={"error": "题目索引无效"}, status_code=400)
    q = questions[idx]
    correct = user_ans == (q.get("answer") or "").strip().upper()

    # ===== 翻书：按题目的章节找老师笔记，塞给 AI 当"教材" =====
    book = load_knowledge_chapter(q.get("chapter", ""))
    book_section = ""
    if book:
        book_section = "\n【老师该章考点笔记（重点依据，优先按它讲，别自己另编一套）】\n" + book

    # ===== 检索：从题库里找出 3 道相似题，也塞给 AI =====
    related = []
    similar_section = ""
    try:
        related = hybrid_search(
            (q.get("question") or "") + " " + (q.get("knowledge_point") or ""),
            top_k=3,
        )
        related = [it for it in related if it.get("id") != q.get("id")]  # 去掉它自己
        if related:
            lines = []
            for it in related:
                lines.append(
                    "【题号 "
                    + str(it.get("id"))
                    + "｜"
                    + str(it.get("chapter"))
                    + "｜"
                    + str(it.get("knowledge_point"))
                    + "】\n"
                    + str(it.get("doc", ""))
                )
            similar_section = "\n【题库里的相似题（可用来举例，或让学生再练）】\n" + "\n".join(
                lines
            )
    except Exception:
        pass

    prompt = (
        "你是「印库」的 AI 助教，在给一个备考的学生讲一道数据结构题。口吻：口语、大白话、讲到点子上就停，别啰嗦。\n"
        f"学生这道题答{('对了' if correct else '错了')}。\n\n"
        f"【题目】{q.get('question', '')}\n"
        f"【选项】{q.get('options', '')}\n"
        f"【标准答案】{q.get('answer', '')}\n"
        f"【人工解析】{q.get('parsing', '')}\n"
        f"【常见错误】{q.get('common_errors', '')}\n"
        f"【学生答的】{user_ans}\n"
        + book_section
        + similar_section
        + "\n\n请用 3~5 句话：①一句话说这道题考什么知识点；②如果答错了，点破他错在哪；③再用大白话把正确思路讲一遍。如果上面给了老师笔记，要结合笔记里的重点和易错点讲。最后另起一行，用「【再练这几道】」开头，把上面相似题里的题号原样抄下来（有几个写几个，不许自己编题号）。"
    )

    ollama_url = "http://127.0.0.1:11434/api/generate"
    try:
        resp = httpx.post(
            ollama_url, json={"model": "qwen2.5:7b", "prompt": prompt, "stream": False}, timeout=60
        )
        data = resp.json()
        return JSONResponse(
            content={
                "ai_explain": data.get("response", ""),
                "book_used": bool(book),  # 是否翻到了老师笔记（True/False）
                "book_chapter": q.get("chapter", ""),  # 翻的是哪一章
                "related": [  # 顺便找到的相似题（给前端用）
                    {
                        "id": it.get("id"),
                        "chapter": it.get("chapter"),
                        "knowledge_point": it.get("knowledge_point"),
                    }
                    for it in related
                ],
            }
        )

    except Exception as e:
        return JSONResponse(
            content={"ai_explain": "", "error": "调用 Ollama 失败：" + str(e)}, status_code=500
        )
