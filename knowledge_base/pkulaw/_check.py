# -*- coding: utf-8 -*-
import json, os
out = os.path.dirname(os.path.abspath(__file__)) + r"\out\chunks_pkulaw.json"
c = json.load(open(out, encoding="utf-8"))
print("总chunk:", len(c))
withtiao = [x for x in c if x["条号"]]
print("带条号chunk:", len(withtiao), " 无条号(整篇):", len(c) - len(withtiao))
print("\n--- 样例:带条号的 ---")
if withtiao:
    x = withtiao[0]
    for k in ["法规名", "条号", "效力层级", "时效性", "法宝引证码"]:
        print(k, "=", x[k])
    print("条文:", x["条文"][:180])
print("\n--- 适航审定指导意见 CLI.4.329570 ---")
for x in c:
    if x["法宝引证码"] == "CLI.4.329570":
        print("法规名=", repr(x["法规名"]))
        print("条文前300:", x["条文"][:300])
        break
