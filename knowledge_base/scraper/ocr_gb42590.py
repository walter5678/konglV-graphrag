# -*- coding: utf-8 -*-
"""GB42590 全量 OCR：渲染38页 → OCR → 缓存每页行到 _gb42590_ocr_raw.json"""
import sys, io, os, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
import fitz
from rapidocr_onnxruntime import RapidOCR

HERE = os.path.dirname(os.path.abspath(__file__))
PDF = os.path.abspath(os.path.join(HERE, "..", "law", "05_标准",
      "GB 42590-2023 民用无人驾驶航空器系统安全要求.pdf"))
RAW = os.path.join(HERE, "_gb42590_ocr_raw.json")
TMP = os.path.join(HERE, "_gb_tmp.png")

ocr = RapidOCR()
doc = fitz.open(PDF)
n = len(doc)
pages = []
t0 = time.time()
for pno in range(n):
    page = doc[pno]
    pix = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
    pix.save(TMP)
    result, _ = ocr(TMP)
    lines = [r[1] for r in result] if result else []
    pages.append({"page": pno + 1, "lines": lines})
    print(f"  第{pno+1}/{n}页 → {len(lines)}行  (累计{time.time()-t0:.0f}s)", flush=True)

with open(RAW, "w", encoding="utf-8") as f:
    json.dump(pages, f, ensure_ascii=False, indent=2)
if os.path.exists(TMP):
    os.remove(TMP)
print(f"\n✅ OCR完成 {n}页 → {RAW}", flush=True)
