# -*- coding: utf-8 -*-
"""
build_inventory_dikongjie.py —— 对 raw/dikongjie_html 的37个源文件做「每文档一行」清单。
复用 fetch_dikongjie 的 parse_title / extract_body（取发布日期、判断有无第X条）。
输出 raw/dikongjie_html/inventory_dikongjie.json。适用范围留空/按标题给提示。
"""
import os, sys, re, json
sys.stdout.reconfigure(encoding="utf-8")
from fetch_dikongjie import parse_title, extract_body, parse_articles

HERE = os.path.dirname(os.path.abspath(__file__))
HTML_DIR = os.path.join(HERE, "..", "raw", "dikongjie_html")
MANIFEST = os.path.join(HTML_DIR, "_manifest.json")
OUTFILE = os.path.join(HTML_DIR, "inventory_dikongjie.json")

# 已在正式库(chunks_all)的重复项（去括号法规名）
DUP_NAMES = {"深圳经济特区低空经济产业促进条例", "苏州市低空经济促进条例"}
# 噪声/非法规候选（E类，暂不决策，先标注）
NOISE_IDS = {"766": "科普资讯文,非法规", "7695": "农技指导意见,非法规",
             "4286": "标准体系建设规划,非规范条文"}


def main():
    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    rows = []
    for m in manifest:
        did, raw_title = m["id"], m["列表标题"]
        region, name, lvl = parse_title(raw_title)
        key = re.sub(r"[（(].*?[)）]", "", name).strip()
        html_path = os.path.join(HTML_DIR, m["html_file"]) if m.get("html_file") else None
        date, has_tiao, n_art = "", False, 0
        if html_path and os.path.exists(html_path):
            html = open(html_path, encoding="utf-8").read()
            body, date = extract_body(html)
            arts = parse_articles(body, mode="条")
            n_art = len(arts)
            has_tiao = n_art > 0
        # 状态判定
        if did in NOISE_IDS:
            status, note = "建议剔除", NOISE_IDS[did]
        elif key in DUP_NAMES:
            status, note = "已入库(重复)", "库中已有,跳过用旧版"
        elif "送审稿" in raw_title or "征求意见" in raw_title:
            status, note = "待定", "送审稿/未生效,元数据需标注"
        else:
            status, note = "待chunk", ""
        rows.append({
            "来源": "dikongjie", "类型": "地方法规" if lvl == "地方性法规" else "地方规范性文件",
            "标题": name, "地区": region, "效力层级": lvl,
            "发布日期": date or None, "有无第X条": has_tiao, "条数": n_art,
            "适用范围": None, "状态": status, "备注": note,
            "文件路径": os.path.relpath(html_path, os.path.join(HERE, "..")) if html_path else None,
            "来源URL": m["url"], "id": did,
        })
    json.dump(rows, open(OUTFILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    n_chunk = sum(1 for r in rows if r["状态"] == "待chunk")
    print(f"完成 {len(rows)} 行 → {OUTFILE}")
    print(f"  待chunk {n_chunk}｜重复 {sum(1 for r in rows if r['状态']=='已入库(重复)')}"
          f"｜建议剔除 {sum(1 for r in rows if r['状态']=='建议剔除')}"
          f"｜待定 {sum(1 for r in rows if r['状态']=='待定')}")
    print(f"  有第X条结构 {sum(1 for r in rows if r['有无第X条'])} / {len(rows)}")


if __name__ == "__main__":
    main()
