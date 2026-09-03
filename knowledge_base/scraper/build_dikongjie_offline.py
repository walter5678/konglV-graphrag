# -*- coding: utf-8 -*-
"""
build_dikongjie_offline.py —— 离线解析 raw/dikongjie_html/ 下已落盘的 39 部地方法规 HTML，
按「第X条」结构化为 chunk 合并进 raw/chunks_all.json。

不联网(避开 dikongjie.com 502/限流)：数据源=本地 HTML + _manifest.json。
解析/清洗/去重逻辑完全复用 fetch_dikongjie.py(parse_title/extract_body/QUAN_MIN 等)，
只把「requests 抓详情页」换成「读本地 html_file」。可重跑(先剔除旧 dikongjie_ 再合并)。
"""
import os, sys, re, json
sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch_dikongjie as fd  # 复用 parse_title/extract_body/parse_articles/SKIP_TITLE/QUAN_MIN

RAW = os.path.join(HERE, "..", "raw")
HTML_DIR = os.path.join(RAW, "dikongjie_html")
MANIFEST = os.path.join(HTML_DIR, "_manifest.json")
FULLTEXT = os.path.join(RAW, "fulltext", "dikongjie.json")
CHUNKS_ALL = os.path.join(RAW, "chunks_all.json")


def main():
    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    print(f"manifest 收录 {len(manifest)} 条")

    allc = json.load(open(CHUNKS_ALL, encoding="utf-8"))
    # 现有库法规名(去括注)用于去重——排除本来就要重建的 dikongjie_ 自身
    exist_names = set()
    for c in allc:
        if str(c.get("chunk_id", "")).startswith("dikongjie_"):
            continue
        n = c.get("法规名", "")
        if n:
            exist_names.add(re.sub(r"[（(].*?[)）]", "", n).strip())

    records, added, skipped_dup, skipped_empty, skipped_noise = [], 0, 0, 0, 0
    seen_keys = set()
    for idx, m in enumerate(manifest, 1):
        did = m["id"]
        raw_title = m.get("列表标题", "")
        html_path = os.path.join(HTML_DIR, m.get("html_file", f"{did}.html"))
        if fd.SKIP_TITLE.search(raw_title):
            skipped_noise += 1
            print(f"  [{idx}] 跳过(非法规): {raw_title[:30]}")
            continue
        if not os.path.exists(html_path):
            print(f"  [{idx}] ⚠ 缺HTML文件: {html_path}")
            continue
        region, name, lvl = fd.parse_title(raw_title)
        key = re.sub(r"[（(].*?[)）]", "", name).strip()
        if key in exist_names or key in seen_keys:
            skipped_dup += 1
            print(f"  [{idx}] 跳过(已有): {name[:30]}")
            continue

        html = open(html_path, encoding="utf-8").read()
        body, date = fd.extract_body(html)
        arts = fd.parse_articles(body, mode="条")
        url = m.get("url", fd.DETAIL.format(did))
        meta = {"法规名": name, "效力层级": lvl, "发布机关": region or "地方",
                "文号": "", "公布日期": date, "生效日期": "", "时效性": "现行有效",
                "来源URL": url}
        n_before = len(records)
        if arts:
            for a in arts:
                text = a["条文"].strip()
                if len(text.replace("\n", "")) < 8:
                    continue
                rec = dict(meta)
                rec.update({"章": a["章"], "节": a["节"], "条号": a["条号"],
                            "条文": text, "chunk_id": f"dikongjie_{did}::{a['条号']}"})
                records.append(rec)
        else:
            full = "\n".join(body).strip()
            if len(full.replace("\n", "")) >= fd.QUAN_MIN:
                rec = dict(meta)
                rec.update({"章": None, "节": None, "条号": "全文",
                            "条文": full, "chunk_id": f"dikongjie_{did}::全文"})
                records.append(rec)
        got = len(records) - n_before
        if got == 0:
            skipped_empty += 1
        else:
            added += 1
            seen_keys.add(key)
        print(f"  [{idx}] {region} {name[:26]} | {lvl} | {got}条")

    os.makedirs(os.path.dirname(FULLTEXT), exist_ok=True)
    json.dump(records, open(FULLTEXT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    allc = [c for c in allc if not str(c.get("chunk_id", "")).startswith("dikongjie_")]
    before = len(allc)
    allc.extend(records)
    json.dump(allc, open(CHUNKS_ALL, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"\n新增法规 {added} 部 / {len(records)} chunk｜跳过(已有){skipped_dup}"
          f"｜跳过(空){skipped_empty}｜跳过(非法规){skipped_noise}")
    print(f"chunks_all: {before} → {len(allc)}")


if __name__ == "__main__":
    main()
