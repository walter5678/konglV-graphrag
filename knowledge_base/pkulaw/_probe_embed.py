# -*- coding: utf-8 -*-
import fitz, glob, os, re
d = r"D:\schoolwork\competition\低空经济无人机法律智能问答比赛\knowledge_base\pkulaw\raw_pdf"
pdfs = sorted(glob.glob(os.path.join(d, "**", "*.pdf"), recursive=True))
TIAO = re.compile(r"第[一二三四五六七八九十百零两0-9]+条")
stub, full, cited_law, cited_case, supersede = [], [], 0, 0, 0
for p in pdfs:
    doc = fitz.open(p); txt = "".join(pg.get_text() for pg in doc); doc.close()
    body = txt.split("附件预览")[0] if "附件预览" in txt else txt
    has_tiao = bool(TIAO.search(body))
    is_stub = ("附件预览" in txt) and (not has_tiao) and (len(txt) < 3000)
    (stub if is_stub else full).append(os.path.basename(p))
    if "本篇引用的法规" in txt or "引用本篇的法规" in txt: cited_law += 1
    if "案例与裁判文书" in txt or "裁判文书" in txt: cited_case += 1
    if "废止" in txt and "依据" in txt: supersede += 1
print("总PDF:", len(pdfs))
print("空壳(附件预览+无第X条+短):", len(stub))
print("有正文全文:", len(full))
print("含'法宝联想-引用法规'块:", cited_law)
print("含'关联案例'块:", cited_case)
print("含'废止依据'信息:", supersede)
print("\n--- 有正文全文的(前25) ---")
for f in full[:25]:
    print("  ", re.sub(r"\(FBMCLI.*", "", f)[:40])
