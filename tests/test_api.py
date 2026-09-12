import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def test_courses():
    assert client.get("/courses").status_code == 200

def test_questions():
    assert client.get("/questions").status_code == 200

def test_learn_questions():
    assert client.get("/learn/questions").status_code == 200

def test_admin_questions():
    assert client.get("/admin/questions").status_code == 200

@pytest.mark.skipif(os.environ.get("CI") == "true", reason="CI 环境没有 Ollama")
def test_rag_search():
    assert client.get("/rag/search", params={"q": "递归"}).status_code == 200

def test_profile_needs_user():
    # 缺 user_id 应 400（说明路由命中、只是校验拦下）
    assert client.get("/profile").status_code == 400

def test_due_needs_user():
    assert client.get("/due").status_code == 400
