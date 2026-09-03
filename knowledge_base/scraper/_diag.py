# -*- coding: utf-8 -*-
import io, re, requests, pdfplumber
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
url = "https://www.caac.gov.cn/XXGK/XXGK/MHGZ/202401/P020240103569247124102.pdf"
r = requests.get(url, headers=H, timeout=90)
print("bytes", len(r.content))
with pdfplumber.open(io.BytesIO(r.content)) as pdf:
    print("pages", len(pdf.pages))
    for i, page in enumerate(pdf.pages[:3]):
        t = page.extract_text() or ""
        print(f"--- page {i} textlen={len(t)} ---")
        print(t[:600])
    full = "\n".join((p.extract_text() or "") for p in pdf.pages)
print("total textlen", len(full))
print("含'第一条':", "第一条" in full, "含'第九十二':", "第九十二" in full)
print("'第..条'次数:", len(re.findall(r'第[一二三四五六七八九十百]+条', full)))
# 看行首形态
for line in full.split("\n"):
    s = line.strip()
    if s.startswith("第") and "条" in s[:8]:
        print("样例条:", repr(s[:40])); break
