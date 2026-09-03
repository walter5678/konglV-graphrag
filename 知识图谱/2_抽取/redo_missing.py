# -*- coding: utf-8 -*-
"""
redo_missing.py —— 找出 llm_cache 未覆盖的单元，重新分批到 batch_1XX.json 供补跑。
（合并脚本按 batch_*.jsonl 通配，故用 100+ 编号可被自动纳入）
"""
import os, sys, json, math
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
UNITS = os.path.join(os.path.dirname(HERE), "1_结构化", "out", "units_normalized.json")
CACHE = os.path.join(HERE, "out", "llm_cache.jsonl")
BDIR = os.path.join(HERE, "batches")

covered = set()
for ln in open(CACHE, encoding="utf-8"):
    try: covered.add(json.loads(ln)["unit_id"])
    except Exception: pass
units = json.load(open(UNITS, encoding="utf-8"))
missing = [u for u in units if u["unit_id"] not in covered]
slim = [{"unit_id": u["unit_id"], "法规名": u.get("法规名"),
         "条号": u.get("条号") or u.get("unit_type"), "条文": u.get("条文")} for u in missing]
B = 40
n = math.ceil(len(slim)/B)
for i in range(n):
    json.dump(slim[i*B:(i+1)*B], open(os.path.join(BDIR, f"batch_{100+i:03d}.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
print(f"缺失单元 {len(missing)} → {n} 个补跑批(batch_100..batch_{100+n-1:03d})")
