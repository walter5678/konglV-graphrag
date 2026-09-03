# -*- coding: utf-8 -*-
"""
merge_batches.py —— 把 batches/out/batch_XXX.jsonl 合并成 out/llm_cache.jsonl。
按 unit_id 去重；报告覆盖率（多少单元已抽 / 缺哪些批）。
之后跑 `python build_llm_extract.py --aggregate` 出 nodes_llm/edges_llm。
"""
import os, sys, re, glob, json
sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
BOUT = os.path.join(HERE, "batches", "out")
UNITS = os.path.join(os.path.dirname(HERE), "1_结构化", "out", "units_normalized.json")
CACHE = os.path.join(HERE, "out", "llm_cache.jsonl")


def main():
    total = len(json.load(open(UNITS, encoding="utf-8")))
    files = sorted(glob.glob(os.path.join(BOUT, "batch_*.jsonl")))
    seen, rows, bad = set(), [], 0
    for f in files:
        for ln in open(f, encoding="utf-8"):
            ln = ln.strip()
            if not ln:
                continue
            try:
                d = json.loads(ln)
            except Exception:
                bad += 1
                continue
            uid = d.get("unit_id")
            if not uid or uid in seen:
                continue
            seen.add(uid); rows.append(d)
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w", encoding="utf-8") as f:
        for d in rows:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    # 缺失批次
    have = {int(re.search(r"batch_(\d+)", os.path.basename(f)).group(1)) for f in files}
    missing = [f"{i:03d}" for i in range(93) if i not in have]
    print(f"✅ 合并 {len(files)} 批 → llm_cache.jsonl")
    print(f"   覆盖单元 {len(rows)}/{total}（{len(rows)*100//total}%）｜坏行 {bad}")
    if missing:
        print(f"   ⚠ 缺失批次({len(missing)}): {missing}")
    else:
        print("   全部 93 批齐全")


if __name__ == "__main__":
    main()
