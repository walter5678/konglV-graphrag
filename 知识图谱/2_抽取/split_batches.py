# -*- coding: utf-8 -*-
"""
split_batches.py —— 把 units_normalized.json 切成批次供 Claude 子代理抽取。
每批一个 json：[{unit_id, 法规名, 条号, 条文}]，写到 batches/batch_XXX.json。
子代理读一批 → 按 extraction_spec 抽取 → 写 batches/out/batch_XXX.jsonl。
"""
import os, sys, json, math
sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
IN = os.path.join(os.path.dirname(HERE), "1_结构化", "out", "units_normalized.json")
BDIR = os.path.join(HERE, "batches")
BATCH = 40

def main():
    os.makedirs(os.path.join(BDIR, "out"), exist_ok=True)
    units = json.load(open(IN, encoding="utf-8"))
    slim = [{"unit_id": u["unit_id"], "法规名": u.get("法规名"),
             "条号": u.get("条号") or u.get("unit_type"), "条文": u.get("条文")}
            for u in units]
    n = math.ceil(len(slim) / BATCH)
    for i in range(n):
        b = slim[i*BATCH:(i+1)*BATCH]
        json.dump(b, open(os.path.join(BDIR, f"batch_{i:03d}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    print(f"✅ {len(slim)} 单元 → {n} 批（每批{BATCH}）→ {BDIR}")

if __name__ == "__main__":
    main()
