# -*- coding: utf-8 -*-
import os, sys, json
sys.stdout.reconfigure(encoding="utf-8")
BASE = r"D:\schoolwork\competition\低空经济无人机法律智能问答比赛"
chp = os.path.join(BASE, "知识图谱", "5_向量库", "out", "children.jsonl")
law_child=case_child=0
law_regs=set()
for ln in open(chp, encoding="utf-8"):
    ln=ln.strip()
    if not ln: continue
    d=json.loads(ln); pid=d.get("parent_id","")
    if pid.startswith("FBMCLI.C") and "::" not in pid:
        case_child+=1
    elif pid.startswith(("CLI.","FBMCLI.")) and "::" in pid:
        law_child+=1; law_regs.add(pid.split("::")[0])
print("向量库 pkulaw法规 child:", law_child, "｜法规数:", len(law_regs))
print("向量库 案例(Case) child:", case_child)

# parents.json 里 Case 数
pj = os.path.join(BASE, "知识图谱", "5_向量库", "out", "parents.json")
if os.path.exists(pj):
    P=json.load(open(pj,encoding="utf-8"))
    if isinstance(P,dict):
        vals=list(P.values())
    else:
        vals=P
    ncase=sum(1 for v in vals if isinstance(v,dict) and (str(v.get("id","")).startswith("FBMCLI.C") or v.get("label")=="Case" or v.get("文书类型")))
    print("parents.json 总", len(vals), "｜疑似Case parent:", ncase)
