# build_index.py
# 真 RAG 第2步：把 yinku.db 里的题转成向量，存进 Chroma 本地文件库
# 运行：印库根目录 venv\Scripts\python.exe build_index.py
import sqlite3

import chromadb
import httpx

from app.config import BASE_DIR, settings
from app.services.rag_service import EMBED_MODEL

DB_PATH = settings.db_path
CHROMA_DIR = str(BASE_DIR / "data" / "chroma_db")
OLLAMA_URL = "http://127.0.0.1:11434"



def get_embedding(text):
    resp = httpx.post(
        OLLAMA_URL + "/api/embeddings",
        json={"model": EMBED_MODEL, "prompt": text},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]


def build_doc(r):
    parts = []
    kp = r["knowledge_point"] or ""
    ch = r["chapter"] or ""
    qs = r["question"] or ""
    ps = r["parsing"] or ""
    if kp:
        parts.append("知识点：" + kp)
    if ch:
        parts.append("章节：" + ch)
    if qs:
        parts.append("题目：" + qs)
    if ps:
        parts.append("解析：" + ps)
    return "\n".join(parts)


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM questions ORDER BY id").fetchall()
    conn.close()
    total = len(rows)
    print("从 yinku.db 读到 " + str(total) + " 道题，开始转向量...")

    client = chromadb.PersistentClient(path=CHROMA_DIR)
    try:
        client.delete_collection("yinku")
    except Exception:
        pass
    col = client.create_collection("yinku")

    ok = 0
    fail = 0
    for i, r in enumerate(rows, 1):
        doc = build_doc(r)
        if not doc.strip():
            fail += 1
            continue
        try:
            vec = get_embedding("search_document: " + doc)
        except Exception as e:
            print("  第 " + str(i) + " 题(" + str(r["id"]) + ")转向量失败: " + str(e))
            fail += 1
            continue
        col.add(
            ids=[r["id"]],
            embeddings=[vec],
            documents=[doc],
            metadatas=[{
                "chapter": r["chapter"] or "",
                "knowledge_point": r["knowledge_point"] or "",
                "type": r["type"] or "",
            }],
        )
        ok += 1
        if i % 20 == 0 or i == total:
            print("  进度 " + str(i) + "/" + str(total) + " (成功 " + str(ok) + ", 失败 " + str(fail) + ")")

    print("索引建完: 共 " + str(col.count()) + " 条向量，存在 " + CHROMA_DIR)
    print("成功 " + str(ok) + " 题，失败 " + str(fail) + " 题")


main()
