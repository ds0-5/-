# 印库 YinKu

面向大学生的数据结构与算法 AI 刷题工具：碎片化刷题 + 遗忘曲线复习 + RAG 溯源讲解。

## 技术栈
FastAPI · SQLite · Chroma 向量库 · 本地 Ollama(qwen2.5:7b / nomic-embed-text) · BM25 + RRF 混合检索

## 环境要求
- Python 3.10+
- 本地跑 Ollama，并拉取模型：qwen2.5:7b、nomic-embed-text

## 运行
1. 创建并激活虚拟环境，安装依赖
2. 启动 Ollama 服务（保证上面两个模型可用）
3. 启动后端：uvicorn app.main:app --reload
4. 浏览器打开 web/ 下的页面（practice.html 等）

## API 端点
- /courses、/questions、/check：以题代练
- /review、/due：复习与待复习
- /learn/questions：专项练习
- /rag/search、/rag/explain：RAG 搜题与讲解
- /admin/*：题目增删改
- /profile、/stats/weakpoints、/recommend：档案与薄弱点推荐

## 目录结构
- app/api/routers/：接口层
- app/services/：业务逻辑（quiz_service、rag_service）
- app/config.py：配置
