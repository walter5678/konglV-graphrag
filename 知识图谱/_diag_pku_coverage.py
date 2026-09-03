# -*- coding: utf-8 -*-
"""核查 pkulaw 来源在 chunks_all / 向量库children / 图 三处的覆盖。"""
import os, sys, json
sys.stdout.reconfigure(encoding="utf-8")

BASE = r"D:\schoolwork\competition\低空经济无人机法律智能问答比赛"
KB = os.path.join(BASE, "knowledge_base")

def is_pku(s):
    return s.startswith(("CLI.", "FBMCLI."))

# 1) chunks_all.json 各来源计数
chunks = json.load(open(os.path.join(KB, "raw", "chunks_all.json"), encoding="utf-8"))
from collections import Counter
def src_of(cid):
    if cid.startswith(("CLI.", "FBMCLI.")): return "pkulaw"
    if cid.startswith("dikongjie_"): return "dikongjie"
    if cid.startswith("local_"): return "local"
    if cid.startswith("adminreg_"): return "adminreg"
    if cid.startswith("gb4"): return "gb"
    return "existing/other"
c = Counter(src_of(x.get("chunk_id","")) for x in chunks)
print("[chunks_all] 总", len(chunks), "｜按来源:", dict(c))

# 2) 向量库 children.jsonl 里 pkulaw parent
chp = os.path.join(BASE, "知识图谱", "5_向量库", "out", "children.jsonl")
pku_child = tot_child = 0
pku_parents = set()
for ln in open(chp, encoding="utf-8"):
    ln=ln.strip()
    if not ln: continue
    d=json.loads(ln); tot_child+=1
    pid = d.get("parent_id","")
    if is_pku(pid):
        pku_child+=1; pku_parents.add(pid.split("::")[0])
print("[children.jsonl] 总child", tot_child, "｜pkulaw child", pku_child, "｜pkulaw法规数(按CLI)", len(pku_parents))

# 3) inventory_pkulaw: 保留的法规 vs 案例总数
inv = json.load(open(os.path.join(KB, "pkulaw", "out", "inventory_pkulaw.json"), encoding="utf-8"))
items = inv if isinstance(inv, list) else inv.get("items", inv.get("records", []))
if isinstance(inv, dict) and not items:
    # 可能是 {cli:record}
    items = list(inv.values())
kept = sum(1 for x in items if isinstance(x,dict) and x.get("keep"))
cases = sum(1 for x in items if isinstance(x,dict) and str(x.get("cli","")).startswith("FBMCLI.C"))
print("[inventory_pkulaw] 条目", len(items), "｜keep=True", kept, "｜案例(FBMCLI.C)", cases)
