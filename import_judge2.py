# 印库扩题库：把老师 04_题库.json 里的判断题转成选择题格式，追加进 yinku.db
# 运行位置：印库根目录（和 app、data 平级）
# 运行命令：venv\Scripts\python.exe import_judge2.py
import json
import sqlite3

SRC = r"C:\Users\36085\Desktop\数据结构与算法知识库\04_题库.json"   # 老师题库（只读）
DB_PATH = r"C:\Users\36085\Desktop\印库\data\yinku.db"              # 目标数据库

# 1) 读老师题库，取判断题
with open(SRC, encoding="utf-8") as f:
    data = json.load(f)
judge_list = data["questions"]["judge"]
print(f"从老师题库读到判断题 {len(judge_list)} 道")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# 2) 防重复保险：库里已存在判断题(type=judge)就退出，避免跑两次导重
existing = cur.execute("SELECT COUNT(*) FROM questions WHERE type='judge'").fetchone()[0]
if existing > 0:
    print(f"❌ 库里已有 {existing} 道判断题，脚本拒绝重复导入。若确需重导，请先手动清空。")
    conn.close()
    raise SystemExit

# 3) 找现有最大 q 编号（q098 -> 从 q099 开始接）
max_no = 0
for (rid,) in cur.execute("SELECT id FROM questions").fetchall():
    if rid.startswith("q") and rid[1:].isdigit():
        max_no = max(max_no, int(rid[1:]))
print(f"现有最大编号 q{max_no:03d}，新判断题将从 q{max_no + 1:03d} 开始")

# 4) 转换并插入
inserted = 0
for i, j in enumerate(judge_list):
    ans_raw = str(j.get("answer", "")).strip()
    if ans_raw == "√":
        answer = "A"
    elif ans_raw in ("×", "X", "x"):
        answer = "B"
    else:
        print(f"⚠️ 跳过无法识别的答案: {j.get('id')} answer={ans_raw!r}")
        continue

    new_id = "q" + str(max_no + 1 + inserted).zfill(3)   # q099, q100, ...
    chapter = f"第{int(j.get('chapter', 0))}章" if j.get("chapter") is not None else ""

    cur.execute(
        "INSERT INTO questions (id, course, chapter, knowledge_point, type, difficulty, question, options, answer, parsing, common_errors) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            new_id,
            "数据结构与算法",
            chapter,
            j.get("topic", ""),
            "judge",
            "medium",
            j.get("question", ""),
            json.dumps({"A": "正确", "B": "错误"}, ensure_ascii=False),
            answer,
            j.get("note", ""),      # 老师备注当解析用（有就显示，没有留空）
            "",
        ),
    )
    inserted += 1

conn.commit()
total = cur.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
conn.close()
print(f"✅ 已导入 {inserted} 道判断题，题库当前共 {total} 道题")
