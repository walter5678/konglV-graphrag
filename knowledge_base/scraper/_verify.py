# -*- coding: utf-8 -*-
import os, sys, re
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
D = r"D:\schoolwork\competition\低空经济无人机法律智能问答比赛\knowledge_base\law\01_法律"
# distinctive keyword per file
checks = {
 "中华人民共和国民用航空法.html": "民用航空",
 "中华人民共和国治安管理处罚法.html": "治安管理",
 "中华人民共和国刑法.html": "刑罚",
 "中华人民共和国测绘法.html": "测绘",
 "中华人民共和国数据安全法.html": "数据安全",
 "中华人民共和国个人信息保护法.html": "个人信息",
 "中华人民共和国反恐怖主义法.html": "恐怖",
 "中华人民共和国突发事件应对法.html": "突发事件",
 "中华人民共和国国家安全法.html": "国家安全",
 "中华人民共和国网络安全法.html": "网络安全",
 "中华人民共和国民法典-第七编侵权责任.html": "侵权责任",
}
for fn, kw in checks.items():
    p = os.path.join(D, fn)
    if not os.path.exists(p):
        print(f"MISSING {fn}"); continue
    b = open(p,"rb").read()
    txt = None
    for enc in ("utf-8","gb18030"):
        try:
            t = b.decode(enc)
            # heuristic: pick decode that yields the keyword
            if kw in t or "第一条" in t:
                txt = t; used=enc; break
        except Exception: pass
    if txt is None:
        txt = b.decode("utf-8","ignore"); used="utf-8?"
    plain = re.sub(r"<[^>]+>"," ",txt)
    art = len(re.findall(r"第[一二三四五六七八九十百零两]+条", plain))
    haskw = kw in plain
    has1 = ("第一条" in plain) or ("第 一 条" in plain)
    verdict = "OK" if (haskw and art>=3) else "SUSPECT"
    print(f"[{verdict}] {fn}  size={len(b)} enc={used} kw({kw})={haskw} 第一条={has1} 条数={art}")