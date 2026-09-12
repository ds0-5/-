# RAG 检索引擎 + 题库向量索引同步（被 admin / rag 两个路由共用）
import math
import os
import re
import sqlite3

import chromadb
import httpx

from app.config import BASE_DIR, settings

DATA_DIR = str(BASE_DIR / "data")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma_db")
EMBED_MODEL = "nomic-embed-text"
OLLAMA_URL = "http://127.0.0.1:11434"
DB_PATH = settings.db_path

# 全局缓存：Chroma 只连一次，不用每次请求都重连
_chroma_client = None
_chroma_col = None
# BM25 内存索引缓存（admin 改题后 invalidate 让它重建）
_BM25 = None
_BM25_IDS = []

_STOP = set("的和与及或是在对其为了一个也等都你我会把这被把让给从被向把于并且但如如果当用将才又很最把被着过".split())


def get_col():
    global _chroma_client, _chroma_col
    if _chroma_col is None:
        _chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
        _chroma_col = _chroma_client.get_collection("yinku")
    return _chroma_col


def embed(text):
    resp = httpx.post(OLLAMA_URL + "/api/embeddings",
                      json={"model": EMBED_MODEL, "prompt": "search_query: " + text}, timeout=60)
    resp.raise_for_status()
    return resp.json()["embedding"]


def embed_doc(text):
    resp = httpx.post(OLLAMA_URL + "/api/embeddings",
                      json={"model": EMBED_MODEL, "prompt": "search_document: " + text}, timeout=60)
    resp.raise_for_status()
    return resp.json()["embedding"]


def build_question_doc(r):
    parts = []
    if r["knowledge_point"]:
        parts.append("知识点：" + r["knowledge_point"])
    if r["chapter"]:
        parts.append("章节：" + r["chapter"])
    if r["question"]:
        parts.append("题目：" + r["question"])
    if r["parsing"]:
        parts.append("解析：" + r["parsing"])
    return "\n".join(parts)


def index_question_by_id(qid):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    r = conn.execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()
    conn.close()
    if not r:
        return
    doc = build_question_doc(r)
    try:
        vec = embed_doc(doc)
        get_col().upsert(ids=[r["id"]], embeddings=[vec], documents=[doc],
                         metadatas=[{"chapter": r["chapter"] or "", "knowledge_point": r["knowledge_point"] or "", "type": r["type"] or ""}])
    except Exception as e:
        print("索引同步失败(" + str(qid) + "): " + str(e))
    invalidate_bm25()


def delete_question_from_index(qid):
    try:
        get_col().delete(ids=[qid])
    except Exception:
        pass
    invalidate_bm25()


def invalidate_bm25():
    global _BM25, _BM25_IDS
    _BM25 = None
    _BM25_IDS = []


def _tok(t):
    if not t:
        return []
    toks = re.findall(r'[a-zA-Z0-9]+', t.lower())
    for seg in re.findall(r'[\u4e00-\u9fff]+', t):
        toks += list(seg)                                       # 单字
        if len(seg) > 1:
            toks += [seg[i:i + 2] for i in range(len(seg) - 1)]  # 双字
    return toks


def _bm25_index():
    global _BM25, _BM25_IDS
    if _BM25:
        return _BM25, _BM25_IDS
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id,chapter,knowledge_point,question,parsing,common_errors FROM questions ORDER BY id").fetchall()
    conn.close()
    corpus, ids = [], []
    for r in rows:
        doc = " ".join(filter(None, ["章节：" + (r["chapter"] or ""), "知识点：" + (r["knowledge_point"] or ""),
                                     "题目：" + (r["question"] or ""), "解析：" + (r["parsing"] or ""), "易错：" + (r["common_errors"] or "")]))
        corpus.append(_tok(doc))
        ids.append(r["id"])
    n = len(corpus)
    df = {}
    for d in corpus:
        for t in set(d):
            df[t] = df.get(t, 0) + 1
    avg = sum(len(d) for d in corpus) / n if n else 0
    k1, b = 1.5, 0.75
    idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
    _BM25 = (corpus, idf, avg, k1, b, n)
    _BM25_IDS = ids
    return _BM25, _BM25_IDS


def bm25_search(q, top_n=20):
    (corpus, idf, avg, k1, b, n), _ = _bm25_index()
    qt = _tok(q)
    if not qt:
        return {}
    sc = {}
    for i, doc in enumerate(corpus):
        if not doc:
            continue
        dl = len(doc)
        freq = {}
        for t in doc:
            freq[t] = freq.get(t, 0) + 1
        s = 0.0
        for t in set(qt):
            if t not in idf:
                continue
            f = freq.get(t, 0)
            if f == 0:
                continue
            s += idf[t] * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avg))
        if s > 0:
            sc[_BM25_IDS[i]] = s
    ranked = sorted(sc.items(), key=lambda x: -x[1])[:top_n]
    return {i: r + 1 for r, (i, _) in enumerate(ranked)}


def rrf(rankings, k=60):
    fused = {}
    for rk in rankings:
        for i, rank in rk.items():
            fused[i] = fused.get(i, 0.0) + 1.0 / (k + rank)
    return sorted(fused.items(), key=lambda x: -x[1])


def hybrid_search(q, top_k=3, cand=12):
    col = get_col()
    vec = embed(q)
    res = col.query(query_embeddings=[vec], n_results=cand)
    dense_ids = res["ids"][0]
    dense_dist = res["distances"][0]
    dense_rank = {dense_ids[i]: i + 1 for i in range(len(dense_ids))}
    sparse_rank = bm25_search(q, top_n=cand)
    fused = rrf([dense_rank, sparse_rank])
    picked = [p[0] for p in fused[:top_k]]
    if not picked:
        return []
    mr = col.get(ids=picked, include=["metadatas", "documents"])
    order = {mid: i for i, mid in enumerate(mr["ids"])}
    out = []
    for mid in picked:
        idx = order.get(mid)
        if idx is None:
            continue
        out.append({
            "id": mid,
            "chapter": mr["metadatas"][idx].get("chapter", ""),
            "knowledge_point": mr["metadatas"][idx].get("knowledge_point", ""),
            "type": mr["metadatas"][idx].get("type", ""),
            "doc": mr["documents"][idx],
            "distance": round(dense_dist[dense_ids.index(mid)], 4) if mid in dense_ids else None,
            "rrf_score": round(dict(fused)[mid], 6),
        })
    return out
