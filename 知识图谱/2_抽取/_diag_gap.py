# -*- coding: utf-8 -*-
"""诊断 llm_cache 相对新库 units_normalized 的增量缺口。"""
import os, sys, json
sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
IN = os.path.join(os.path.dirname(HERE), "1_结构化", "out", "units_normalized.json")
CACHE = os.path.join(HERE, "out", "llm_cache.jsonl")

units = json.load(open(IN, encoding="utf-8"))
unit_ids = [u["unit_id"] for u in units]
uset = set(unit_ids)

done = set()
dup = 0
for ln in open(CACHE, encoding="utf-8"):
    ln = ln.strip()
    if not ln:
        continue
    try:
        uid = json.loads(ln)["unit_id"]
    except Exception:
        continue
    if uid in done:
        dup += 1
    done.add(uid)

todo = [u for u in units if u["unit_id"] not in done]
orphan = done - uset

# 按来源前缀归类待抽取
from collections import Counter
def src_of(uid):
    if uid.startswith("dikongjie_"):
        return "dikongjie"
    if uid.startswith(("CLI.", "FBMCLI.")):
        return "pkulaw"
    return "other/existing"
cnt = Counter(src_of(u["unit_id"]) for u in todo)

print(f"新库 units            : {len(units)}")
print(f"cache 去重后已抽 unit  : {len(done)}  (重复行 {dup})")
print(f"cache 孤儿(不在新库)   : {len(orphan)}")
print(f"待抽取(新库-已抽)      : {len(todo)}")
print(f"  按来源: {dict(cnt)}")
print("  待抽取样例:")
for u in todo[:8]:
    print("   ", u["unit_id"], "｜", u.get("法规名"))
