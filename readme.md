# 印库 YinKu

面向大学生的数据结构与算法 AI 刷题工具：碎片化刷题 + 遗忘曲线复习 + RAG 溯源讲解。

## 技术栈
FastAPI · SQLite · Chroma 向量库 · 本地 Ollama(qwen2.5:7b / nomic-embed-text) · BM25 + RRF 混合检索

## 环境要求
- Python 3.10+
- 本地跑 Ollama，并拉取模型：qwen2.5:7b、nomic-embed-text

## 上手步骤

1. 创建并激活虚拟环境

       python -m venv venv
       venv\Scripts\activate          # Windows
       source venv/bin/activate       # macOS / Linux

2. 安装依赖

       pip install -r requirements.txt

3. 准备配置文件

       copy .env.example .env         # Windows
       cp .env.example .env           # macOS / Linux

4. 拉取 Ollama 模型（需先装好 Ollama 并让它运行）

       ollama pull qwen2.5:7b
       ollama pull nomic-embed-text

5. 重建向量索引（必做，向量库不进仓库）

       python build_index.py

6. 启动后端

       uvicorn app.main:app --reload

启动后浏览器打开 `web/` 下的页面（`practice.html` 等）。

## 跑测试

    pytest

注意：`test_rag_search` 需要本机 Ollama 正在运行。

## API 端点
- `/courses`、`/questions`、`/check`：以题代练
- `/review`、`/due`：复习与待复习
- `/learn/questions`：专项练习
- `/rag/search`、`/rag/explain`：RAG 搜题与讲解
- `/wrong`、`/stats/weakpoints`：错题本与薄弱点
- `/admin/*`：题目增删改
- `/profile`、`/recommend`：档案与推荐

## 目录结构
- `app/api/routers/`：接口层
- `app/services/`：业务逻辑（quiz_service、rag_service）
- `app/config.py`：配置（所有可变配置走 `.env`）
- `web/`：前端页面（纯 HTML）
- `tests/`：测试
- `data/`：数据库与向量库（向量库可用 `build_index.py` 重建）
