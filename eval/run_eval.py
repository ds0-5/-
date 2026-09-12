# eval/run_eval.py
# 用途：拿 cases.md 里的考卷，去考「搜题」功能，算出命中率
# 运行：在印库根目录跑  venv\Scripts\python.exe eval\run_eval.py
#
# 判分分两级：
#   完全命中 = 搜到的题里，有一道的知识点和期望一模一样
#   大致命中 = 搜到的题里，有一道的知识点和期望共享 2 个以上连续汉字（同义 / 同主题）

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.rag_service import hybrid_search

CASES = Path(__file__).resolve().parent / "cases.md"
TOP_K = 3
MIN_SHARE = 2          # 共享几个连续汉字才算「大致命中」


def load_cases():
    """从 cases.md 的表格里读出 (问题, 期望知识点) 列表"""
    cases = []
    for line in CASES.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3 or not cells[0].isdigit():
            continue
        cases.append((cells[1], cells[2]))
    return cases


def shares_text(a, b):
    """a 里有没有连续 MIN_SHARE 个字，出现在 b 里"""
    if not a or not b:
        return False
    for i in range(len(a) - MIN_SHARE + 1):
        if a[i:i + MIN_SHARE] in b:
            return True
    return False


def judge(expect, got_list):
    """判分：'strict' 完全一致 / 'loose' 大致一致 / None 没中"""
    if expect in got_list:
        return "strict"
    for g in got_list:
        if shares_text(expect, g):
            return "loose"
    return None


def main():
    cases = load_cases()
    print("考卷共 " + str(len(cases)) + " 题，开始考试...")
    print()

    strict = 0
    loose = 0
    for i, (question, expect) in enumerate(cases, 1):
        try:
            items = hybrid_search(question, top_k=TOP_K)
        except Exception as e:
            print(str(i).rjust(2) + ". 出错  " + question + "  → " + str(e))
            continue

        got = [it.get("knowledge_point", "") for it in items]
        verdict = judge(expect, got)
        if verdict == "strict":
            strict += 1
            loose += 1
            mark = "命中"
        elif verdict == "loose":
            loose += 1
            mark = "大致"
        else:
            mark = "没中"

        print(str(i).rjust(2) + ". " + mark + "  " + question)
        if verdict is None:
            print("      期望: " + expect)
            print("      实际: " + " / ".join(got))

    total = len(cases)
    print()
    print("=" * 52)
    print("完全命中: " + str(strict) + " / " + str(total) + " = " + str(round(strict / total * 100)) + "%")
    print("大致命中: " + str(loose) + " / " + str(total) + " = " + str(round(loose / total * 100)) + "%")
    print("（大致命中 = 完全命中 + 搜到了同义 / 同主题的知识点）")
    print("=" * 52)


main()
