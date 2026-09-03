# -*- coding: utf-8 -*-
"""
fetch_dikongjie_raw.py —— 只抓源文件：把 低空界(dikongjie.com) 法律法规库 每条法规的
详情页【原始 HTML】原样落盘，不清洗、不解析、不 chunk、不碰 chunks_all.json。

产出：
  raw/dikongjie_html/<id>.html          每条详情页原始 HTML
  raw/dikongjie_html/_manifest.json     [{id, 列表标题, url, html_file, bytes, status}]

后续如需 chunk，另跑解析脚本读这些本地 HTML 即可（离线、可反复调参）。
"""
import os, sys, re, json, time
sys.stdout.reconfigure(encoding="utf-8")
import requests
from bs4 import BeautifulSoup

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "..", "raw", "dikongjie_html")
MANIFEST = os.path.join(OUT_DIR, "_manifest.json")
LIST_URL = "https://dikongjie.com/Laws-regulations/?page={}"
DETAIL = "https://dikongjie.com/{}.html"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}


def get(url, tries=3):
    for _ in range(tries):
        try:
            r = requests.get(url, headers=H, timeout=30)
            r.encoding = r.apparent_encoding or r.encoding
            if r.status_code == 200:
                return r.text
        except Exception:
            time.sleep(2)
    return ""


def collect_list():
    """遍历分页收集 (id, 列表标题)。到空页或无新id停。"""
    items, seen = [], set()
    for pg in range(1, 15):
        html = get(LIST_URL.format(pg))
        if not html:
            break
        soup = BeautifulSoup(html, "lxml")
        page_ids = []
        for a in soup.find_all("a", href=True):
            m = re.search(r"dikongjie\.com/(\d{3,6})\.html", a["href"])
            txt = a.get_text(strip=True)
            if m and txt and len(txt) > 8:
                page_ids.append((m.group(1), txt[:120]))
        new = [(i, t) for i, t in page_ids if i not in seen]
        if not new:
            break
        for i, t in new:
            seen.add(i); items.append((i, t))
        print(f"  第{pg}页: +{len(new)} 条 (累计 {len(items)})")
        time.sleep(1)
    return items


def main():
    print("收集列表...")
    items = collect_list()
    print(f"列表收集到 {len(items)} 条法规")
    if not items:
        print("⚠ 列表为空（网站502/限流？）——中止，不写任何文件。稍后重试。")
        return

    os.makedirs(OUT_DIR, exist_ok=True)
    # 断点续跑：已存在且非空的 html 跳过下载
    manifest, ok, skipped, failed = [], 0, 0, 0
    for idx, (did, raw_title) in enumerate(items, 1):
        html_path = os.path.join(OUT_DIR, f"{did}.html")
        if os.path.exists(html_path) and os.path.getsize(html_path) > 500:
            skipped += 1
            manifest.append({"id": did, "列表标题": raw_title, "url": DETAIL.format(did),
                             "html_file": f"{did}.html", "bytes": os.path.getsize(html_path),
                             "status": "cached"})
            print(f"  [{idx}/{len(items)}] 已存在，跳过: {raw_title[:34]}")
            continue
        html = get(DETAIL.format(did))
        if not html:
            failed += 1
            manifest.append({"id": did, "列表标题": raw_title, "url": DETAIL.format(did),
                             "html_file": None, "bytes": 0, "status": "failed"})
            print(f"  [{idx}/{len(items)}] ✗ 下载失败: {raw_title[:34]}")
            continue
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        ok += 1
        manifest.append({"id": did, "列表标题": raw_title, "url": DETAIL.format(did),
                         "html_file": f"{did}.html", "bytes": len(html.encode("utf-8")),
                         "status": "ok"})
        print(f"  [{idx}/{len(items)}] ✓ {raw_title[:34]} ({len(html)}字符)")
        time.sleep(1)

    json.dump(manifest, open(MANIFEST, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n完成：新下载 {ok}｜已缓存跳过 {skipped}｜失败 {failed}｜共 {len(items)} 条")
    print(f"HTML 目录: {OUT_DIR}")
    print(f"清单: {MANIFEST}")


if __name__ == "__main__":
    main()
