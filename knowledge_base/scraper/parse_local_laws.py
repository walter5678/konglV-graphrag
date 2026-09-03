# -*- coding: utf-8 -*-
"""
parse_local_laws.py —— 解析本地已下载的 law/01_法律 与 law/02_行政法规 的 HTML 全文，
按「第X条」切分为 chunk，写入 raw/fulltext/local_laws.json 并合并进 raw/chunks_all.json。
与现有库按「法规名」去重（民航法、飞行管理暂行条例等已入库的跳过）。
刑法为 PDF，本脚本只处理 HTML，PDF 另行处理。
"""
import os, sys, re, json, glob
sys.stdout.reconfigure(encoding="utf-8")
from fetch_fulltext import extract_paragraphs, parse_articles

HERE = os.path.dirname(os.path.abspath(__file__))
KB = os.path.join(HERE, "..")
OUT = os.path.join(KB, "raw")
FULLTEXT = os.path.join(OUT, "fulltext", "local_laws.json")
CHUNKS_ALL = os.path.join(OUT, "chunks_all.json")

DIRS = [("law/01_法律", "法律"), ("law/02_行政法规", "行政法规")]

# 关键元数据映射（法规名含关键词 -> 元数据），与法规清单总表口径一致
META_MAP = {
    "治安管理处罚法": ("主席令(2025修订)", "2025-06-27", "2026-01-01", "现行有效(2026版)",
        "违规飞行/黑飞扰序、扰乱公共场所秩序、妨害公共安全的行政处罚"),
    "个人信息保护法": ("主席令第91号", "2021-08-20", "2021-11-01", "现行有效",
        "无人机航拍/巡检采集人脸、车牌等个人信息的合规"),
    "数据安全法": ("主席令第84号", "2021-06-10", "2021-09-01", "现行有效",
        "无人机采集/传输测绘、遥感等数据的安全管理"),
    "网络安全法": ("主席令第53号(2016)", "2016-11-07", "2017-06-01", "现行有效(2025修正待核)",
        "无人机联网系统(UOM/云系统)网络与数据安全"),
    "反恐怖主义法": ("主席令第36号(2018修正)", "2015-12-27", "2016-01-01", "现行有效",
        "重点目标/大型活动上空无人机反恐管制"),
    "国家安全法": ("主席令第29号", "2015-07-01", "2015-07-01", "现行有效",
        "涉国家安全的低空管控总则性依据"),
    "测绘法": ("主席令第67号(2017修订)", "2017-04-27", "2017-07-01", "现行有效",
        "无人机航空摄影测量的测绘资质与成果管理"),
    "突发事件应对法": ("主席令(2024修订)", "2024-06-28", "2024-11-01", "现行有效(2024版)",
        "应急救援/灾害监测无人机的应急征用与协同"),
    "侵权责任": ("主席令第45号(民法典)", "2020-05-28", "2021-01-01", "现行有效",
        "无人机坠落致人损害、高度危险作业责任、隐私侵权"),
    "无线电管理条例": ("国务院、中央军委令第672号", "2016-11-11", "2016-12-01", "现行有效",
        "无人机测控/图传/导航频率与无线电台(站)管理"),
    "飞行基本规则": ("国务院、中央军委令(2007修订)", "2000-07-24", "2001-08-01", "现行有效",
        "国家空域划分与飞行的基本规则(上位空域规则)"),
    "民用机场管理条例": ("国务院令第553号(2019修订)", "2009-04-13", "2009-07-01", "现行有效",
        "民用机场净空保护区，禁止无人机干扰航空器起降"),
    "通用航空飞行管制条例": ("国务院、中央军委令第371号", "2003-01-10", "2003-05-01", "现行有效",
        "通用航空(含无人机)飞行计划申请、空域使用、飞行管制"),
    "国籍登记条例": ("国务院令第188号", "1997-10-21", "1997-10-21", "现行有效",
        "民用航空器国籍登记(适航/登记制度参照)"),
    "测绘成果管理条例": ("国务院令第469号", "2006-05-27", "2006-09-01", "现行有效",
        "无人机航测成果的汇交、保管与涉密管理"),
    "外国民用航空器飞行管理规则": ("国务院、中央军委", "1979-02-23", "1979-02-23", "现行有效",
        "外国民用航空器入境飞行(边缘相关)"),
}

def meta_for(name):
    for k, v in META_MAP.items():
        if k in name:
            return v
    return ("", "", "", "有效", "")

def slugify(name):
    return re.sub(r"[^\w]", "_", name)[:40]

def main():
    allc = json.load(open(CHUNKS_ALL, encoding="utf-8"))
    exist = set(re.sub(r"[（(].*?[)）·\-]", "", c.get("法规名","")).strip() for c in allc)

    records = []
    summary = []
    for subdir, level in DIRS:
        for fp in sorted(glob.glob(os.path.join(KB, subdir, "*.html"))):
            fname = os.path.splitext(os.path.basename(fp))[0]
            name = fname.replace("-", "·")  # 民法典-第七编 -> 民法典·第七编
            key = re.sub(r"[（(].*?[)）·\-]", "", name).strip()
            # 去重：已入库法规跳过
            if any(key.startswith(e) or e.startswith(key) for e in exist if len(e) > 4):
                summary.append((name, "跳过(已入库)", 0))
                continue
            html = open(fp, encoding="utf-8", errors="ignore").read()
            paras = extract_paragraphs(html)
            arts = parse_articles(paras, mode="条")
            docno, pub, eff, status, scope = meta_for(name)
            meta = {"法规名": name, "效力层级": level, "发布机关": "全国人大常委会" if level=="法律" else "国务院",
                    "文号": docno, "公布日期": pub, "生效日期": eff, "时效性": status or "有效",
                    "来源URL": f"(本地文件) {subdir}/{fname}.html", "适用范围": scope}
            n0 = len(records)
            for a in arts:
                text = a["条文"].strip()
                if len(text.replace("\n","")) < 8:
                    continue
                rec = {k: meta[k] for k in ["法规名","效力层级","发布机关","文号","公布日期","生效日期","时效性","来源URL"]}
                rec.update({"章": a["章"], "节": a["节"], "条号": a["条号"], "条文": text,
                            "chunk_id": f"local_{slugify(name)}::{a['条号']}"})
                records.append(rec)
            summary.append((name, level, len(records)-n0))

    # 合并
    os.makedirs(os.path.dirname(FULLTEXT), exist_ok=True)
    json.dump(records, open(FULLTEXT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    allc = [c for c in allc if not str(c.get("chunk_id","")).startswith("local_")]
    before = len(allc); allc.extend(records)
    json.dump(allc, open(CHUNKS_ALL, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("逐部解析结果:")
    for name, lvl, n in summary:
        print(f"  {n:4d}条  [{lvl}]  {name}")
    parts = len([s for s in summary if s[2] > 0])
    print(f"\n新增 {parts} 部 / {len(records)} chunk｜chunks_all: {before} → {len(allc)}")

if __name__ == "__main__":
    main()
