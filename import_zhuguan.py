# 运行：印库根目录 venv\Scripts\python.exe import_zhuguan.py
# 第2铲：把老师题库里的主观题（填空/应用/综合）导入 yinku.db
import json
import sqlite3

SRC = r"C:\Users\36085\Desktop\数据结构与算法知识库\04_题库.json"
DB_PATH = r"C:\Users\36085\Desktop\印库\data\yinku.db"

with open(SRC, encoding="utf-8") as f:
    data = json.load(f)

# 主观题三种题型
KINDS = {"fill": "fill", "apply": "apply", "comprehensive": "comprehensive"}

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# 防重复保险：库里已存在主观题就拒绝重跑
existing = cur.execute(
    "SELECT COUNT(*) FROM questions WHERE type IN ('fill','apply','comprehensive')"
).fetchone()[0]
if existing > 0:
    print(f"❌ 库里已有 {existing} 道主观题，脚本拒绝重复导入。")
    conn.close()
    raise SystemExit

# 算现有最大 q 编号（q001~q213 -> 下一题从 q214 开始）
max_no = 0
for (rid,) in cur.execute("SELECT id FROM questions").fetchall():
    if rid.startswith("q") and rid[1:].isdigit():
        max_no = max(max_no, int(rid[1:]))

inserted = 0
for t, db_type in KINDS.items():
    lst = data["questions"].get(t, [])
    for j in lst:
        new_id = "q" + str(max_no + 1 + inserted).zfill(3)
        chapter_num = j.get("chapter")
        chapter = f"第{int(chapter_num)}章" if chapter_num is not None else ""
        cur.execute(
            "INSERT INTO questions (id, course, chapter, knowledge_point, type, difficulty, question, options, answer, parsing, common_errors) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                new_id,
                "数据结构与算法",
                chapter,
                j.get("topic", ""),
                db_type,
                "hard",
                j.get("question", ""),
                "{}",
                j.get("answer", ""),
                "",
                "",
            ),
        )
        inserted += 1

conn.commit()
total = cur.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
conn.close()
print(f"✅ 已导入 {inserted} 道主观题（填空/应用/综合），题库当前共 {total} 道题")
