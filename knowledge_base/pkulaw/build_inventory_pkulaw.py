# -*- coding: utf-8 -*-
"""
build_inventory_pkulaw.py —— 对北大法宝 1649 个批量 PDF 做「每文档一行」的清单提取。
不切 chunk。复用 parse_pkulaw 的头部解析(parse_header) + 白/黑名单(decide_keep)。

数据来源：
  - out/missing_body_manifest.json  已有 标题/引证码/record_url/正文长度/附件/zip/file
  - 各 zip 解压到 raw_pdf/  逐个 PDF 解析头部补 机关/公布日期/施行日期/时效性/效力位阶/类别

输出：out/inventory_pkulaw.json  每文档一行：
  来源/类型/效力层级/标题/发布机关/文号/公布日期/施行日期/时效性/法宝引证码/
  是否有附件/正文长度/keep/原因/文件路径/来源URL
适用范围留空（1649个无法批量人工判断，后续对保留项再补）。
"""
import os, sys, re, json, glob, zipfile
sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
PKU_DIR = os.path.join(os.path.dirname(HERE), "law", "北大法宝法律法规")
WORK = os.path.join(HERE, "raw_pdf")
MANIFEST = os.path.join(OUT, "missing_body_manifest.json")
OUTFILE = os.path.join(OUT, "inventory_pkulaw.json")

from parse_pkulaw import parse_header, decide_keep, clean_body, pdf_to_text

CASE_RE = re.compile(r"FBMCLI\.C\.", re.I)


def ensure_extracted():
    """把所有 zip 解压到 raw_pdf/<zip名>/，已存在则跳过。返回 basename->fullpath 映射。"""
    os.makedirs(WORK, exist_ok=True)
    for z in sorted(glob.glob(os.path.join(PKU_DIR, "*.zip"))):
        dest = os.path.join(WORK, os.path.splitext(os.path.basename(z))[0])
        if os.path.isdir(dest) and glob.glob(os.path.join(dest, "**", "*.pdf"), recursive=True):
            continue
        try:
            with zipfile.ZipFile(z) as zf:
                zf.extractall(dest)
            print(f"  解压 {os.path.basename(z)}")
        except Exception as e:
            print(f"  ⚠ 解压失败 {os.path.basename(z)}: {e}")
    # 建 文件名->路径 映射（basename 去掉可能的路径差异）
    idx = {}
    for p in glob.glob(os.path.join(WORK, "**", "*.pdf"), recursive=True):
        idx.setdefault(os.path.basename(p), p)
    return idx


def main():
    print("解压所有 zip...")
    pdf_index = ensure_extracted()
    print(f"raw_pdf 中共 {len(pdf_index)} 个 PDF")

    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    print(f"manifest 条目 {len(manifest)}")

    rows, miss, ncase, nkeep, ndrop = [], 0, 0, 0, 0
    for i, m in enumerate(manifest, 1):
        fname = m.get("file")
        cli = m.get("cli")
        title = m.get("title")
        is_case = bool(CASE_RE.search(cli or "")) or ("司法案例" in (m.get("zip") or ""))
        path = pdf_index.get(fname)
        row = {
            "来源": "pkulaw",
            "类型": "案例" if is_case else "法规",
            "标题": title,
            "法宝引证码": cli,
            "是否有附件": m.get("has_attachment"),
            "正文长度": m.get("body_len"),
            "来源URL": m.get("record_url"),
            "文件路径": os.path.relpath(path, os.path.dirname(HERE)) if path else None,
            "效力层级": None, "发布机关": None, "文号": None,
            "公布日期": None, "施行日期": None, "时效性": None, "法规类别": None,
            "keep": None, "原因": None,
        }
        if is_case:
            # 案例：头部结构不同(案号/法院/案由)，此处只登记，chunk 时另走案例管线
            row["效力层级"] = "司法案例"
            row["keep"] = True
            row["原因"] = "司法案例(单独管线)"
            ncase += 1
        elif path:
            try:
                text = pdf_to_text(path)
                meta = parse_header(text, path)
                body = clean_body(text, meta.get("法规名"))
                keep, reason = decide_keep(meta, body)
                row.update({
                    "效力层级": meta.get("效力层级"), "发布机关": meta.get("发布机关"),
                    "文号": meta.get("文号"), "公布日期": meta.get("公布日期"),
                    "施行日期": meta.get("生效日期"), "时效性": meta.get("时效性"),
                    "法规类别": meta.get("法规类别"), "keep": keep, "原因": reason,
                })
                # 标题以文件名解析为准（parse_header 已处理），补回 row
                if meta.get("法规名"):
                    row["标题"] = meta["法规名"]
                nkeep += 1 if keep else 0
                ndrop += 0 if keep else 1
            except Exception as e:
                row["keep"] = False; row["原因"] = "抽取异常:" + str(e)[:60]
                ndrop += 1
        else:
            miss += 1
            row["keep"] = False; row["原因"] = "PDF文件未找到"
            ndrop += 1
        rows.append(row)
        if i % 200 == 0:
            print(f"  ...{i}/{len(manifest)}")

    json.dump(rows, open(OUTFILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n完成 {len(rows)} 行 → {OUTFILE}")
    print(f"  案例 {ncase}｜法规保留 {nkeep}｜法规丢弃 {ndrop}｜PDF未找到 {miss}")
    # 效力层级分布（法规类）
    dist = {}
    for r in rows:
        if r["类型"] == "法规":
            k = r["效力层级"] or "?"
            dist[k] = dist.get(k, 0) + 1
    print("  法规效力层级分布:", dict(sorted(dist.items(), key=lambda x: -x[1])))


if __name__ == "__main__":
    main()
