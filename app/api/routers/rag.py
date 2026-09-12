import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services.rag_service import OLLAMA_URL, hybrid_search

router = APIRouter()

@router.get("/rag/search")
def rag_search(q: str = "", top_k: int = 3):
    """混合检索调试接口：稠密 + BM25 → RRF"""
    if not q:
        return JSONResponse(content={"error": "请传入 q 参数，例如 /rag/search?q=栈和队列"}, status_code=400)
    try:
        items = hybrid_search(q, top_k=top_k)
    except Exception as e:
        return JSONResponse(content={"error": "检索失败：" + str(e)}, status_code=500)
    return JSONResponse(content={"question": q, "mode": "hybrid(dense+BM25+RRF)", "total": len(items), "results": items})

@router.get("/rag/explain")
def rag_explain(q: str = "", top_k: int = 3):
    """真 RAG 主接口：先检索真实题目，再让 qwen 基于这些题目讲解，答案可溯源"""
    if not q:
        return JSONResponse(content={"error": "请传入 q 参数，例如 /rag/explain?q=栈和队列"}, status_code=400)
    try:
        items = hybrid_search(q, top_k=top_k)
    except Exception as e:
        return JSONResponse(content={"error": "检索失败：" + str(e)}, status_code=500)
    ids = [it["id"] for it in items]
    docs = [it["doc"] for it in items]
    metas = [{"chapter": it["chapter"], "knowledge_point": it["knowledge_point"], "type": it["type"]} for it in items]
    if not ids:
        return JSONResponse(content={"error": "题库里没检索到相关内容"}, status_code=404)
    context = "\n\n".join("【资料" + str(i + 1) + "】(题号 " + ids[i] + "，章节 " + metas[i].get("chapter", "") + ")\n" + docs[i] for i in range(len(ids)))
    instruction = (
        "你是「印库」的数据结构与算法辅导老师。下面是学生题库里检索到的真实资料，"
        "只依据这些资料回答，不许编造资料里没有的内容。\n"
        "要求：口语化、讲清原理和考点、戳中要害就停，不要长篇大论。\n"
        "最后另起一行，用「【参考题号】」开头列出你用到了哪几条资料。\n\n"
        "【检索到的资料】\n" + context + "\n\n【学生问题】\n" + q
    )
    try:
        resp = httpx.post(OLLAMA_URL + "/api/generate", json={"model": "qwen2.5:7b", "prompt": instruction, "stream": False}, timeout=120)
        data = resp.json()
    except Exception as e:
        return JSONResponse(content={"error": "调用 Ollama 失败：" + str(e)}, status_code=500)
    return JSONResponse(content={
        "question": q, "answer": data.get("response", ""),
        "sources": [{"id": ids[i], "chapter": metas[i].get("chapter", ""), "knowledge_point": metas[i].get("knowledge_point", "")} for i in range(len(ids))],
        "context_found": True,
    })
