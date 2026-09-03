# -*- coding: utf-8 -*-
"""
build_admin_regs.py —— 补 4 部行政法规入库:
  无线电管理条例 / 测绘成果管理条例 / 民用机场管理条例 / 通用航空飞行管制条例。

背景(修正旧记忆):这 4 部本地 HTML 早先被判为"空壳(第X条 0 次)",真相是
**lxml 解析器对这些页面返回 0 个 <p>(容错怪癖),换 html.parser 即得 141 个 <p>、
含完整"第X条"正文**。故本脚本强制用 html.parser 抽 <p>,复用 parse_articles 分条,
元数据取自 parse_local_laws.META_MAP,以独立 slug 前缀 adminreg_ 合并进 chunks_all
(不走 parse_local_laws.py,避免其"删所有 local_ 再重写"的重跑删库行为)。
"""
import os, sys, re, json
sys.stdout.reconfigure(encoding="utf-8")
from bs4 import BeautifulSoup
from fetch_fulltext import parse_articles
from parse_local_laws import meta_for, slugify

HERE = os.path.dirname(os.path.abspath(__file__))
KB = os.path.join(HERE, "..")
LAW_DIR = os.path.join(KB, "law", "02_行政法规")
FULLTEXT = os.path.join(KB, "raw", "fulltext", "admin_regs.json")
CHUNKS_ALL = os.path.join(KB, "raw", "chunks_all.json")

TARGETS = [
    "中华人民共和国无线电管理条例",
    "中华人民共和国测绘成果管理条例",
    "民用机场管理条例",
    "通用航空飞行管制条例",
]

# 政府网站页脚样板(紧跟末条后,被 parse_articles 当续行吞入),从此处截断
FOOTER_CUT = re.compile(r"\s*(主办单位[：:]|运行维护单位[：:]|版权所有[：:]|网站标识码)")


def strip_footer(text):
    m = FOOTER_CUT.search(text)
    return text[:m.start()].rstrip() if m else text


def extract_p_texts(html):
    """用 html.parser(lxml 对这些页面漏抽 <p>)取所有段落文本。"""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    paras = []
    for p in soup.find_all("p"):
        t = re.sub(r"\s+", " ", p.get_text(separator=" ", strip=True)).strip()
        if t:
            paras.append(t)
    return paras


def main():
    allc = json.load(open(CHUNKS_ALL, encoding="utf-8"))
    before = len(allc)
    records, summary = [], []

    for name in TARGETS:
        fp = os.path.join(LAW_DIR, name + ".html")
        if not os.path.exists(fp):
            summary.append((name, "文件缺失", 0)); continue
        html = open(fp, encoding="utf-8", errors="ignore").read()
        paras = extract_p_texts(html)
        arts = parse_articles(paras, mode="条")
        docno, pub, eff, status, scope = meta_for(name)
        slug = "adminreg_" + slugify(name)
        n0 = len(records)
        for a in arts:
            text = (a.get("条文") or "").strip()
            text = strip_footer(text)
            if len(text.replace("\n", "")) < 8:
                continue
            records.append({
                "法规名": name, "效力层级": "行政法规", "发布机关": "国务院",
                "文号": docno, "公布日期": pub, "生效日期": eff,
                "时效性": status or "有效",
                "来源URL": f"(本地文件) law/02_行政法规/{name}.html",
                "章": a.get("章"), "节": a.get("节"), "条号": a.get("条号"),
                "条文": text, "chunk_id": f"{slug}::{a.get('条号')}",
            })
        summary.append((name, "行政法规", len(records) - n0))

    # 合并:仅删本脚本自己的 adminreg_ 前缀(幂等,不碰 local_/其它)
    allc = [c for c in allc if not str(c.get("chunk_id", "")).startswith("adminreg_")]
    allc.extend(records)

    os.makedirs(os.path.dirname(FULLTEXT), exist_ok=True)
    json.dump(records, open(FULLTEXT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump(allc, open(CHUNKS_ALL, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("逐部解析:")
    for name, lvl, n in summary:
        print(f"  {n:4d}条  [{lvl}]  {name}")
    print(f"\n新增 {sum(1 for s in summary if s[2] > 0)} 部 / {len(records)} chunk"
          f"｜chunks_all: {before} → {len(allc)}")


if __name__ == "__main__":
    main()
