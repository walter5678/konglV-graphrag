# -*- coding: utf-8 -*-
"""
build_cases.py —— 案例维度：把 531 篇北大法宝司法案例(FBMCLI.C.*)建成独立 Case 子图。

背景(2026-08-06 决策)：这批案例是"当事人为无人机/低空企业"的普通民商事纠纷，援引的多是
《民事诉讼法》《合同法》等程序/民商法(不在无人机法规图内)——811条援引仅~32条能落到图内132部法规。
故不追求"案例→法条"密集连边，而是建**可检索的独立 Case 子图**：
  - Case 节点：规整元数据(案由/案号/审理法院/文书类型/审理程序/相关企业) + 判决摘要 + 全部援引(属性,不丢信息)
  - 援引边：仅对能对齐到图内 Article 的引用建 Case-[:援引]->Article
输入：
  knowledge_base/pkulaw/out/inventory_pkulaw.json     案例元数据行(类型=案例/CLI含.C.)
  knowledge_base/pkulaw/out/case_text_cache.json       {cli: 正文}  (scan 阶段已缓存)
  知识图谱/3_建图/out/graph_export.json                 取 Article/Regulation 做援引对齐
输出(4_案例/out/)：
  nodes_cases.json    Case 节点
  edges_cases.json    援引边(Case->Article)
  stats.json          统计
供 3_建图/build_graph.py 合并进主图。
"""
import os, re, sys, json
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
KG = os.path.dirname(HERE)
ROOT = os.path.dirname(KG)
PKU = os.path.join(ROOT, "knowledge_base", "pkulaw", "out")
GRAPH = os.path.join(KG, "3_建图", "out", "graph_export.json")
OUT = os.path.join(HERE, "out")

# ---- 元数据字段解析 ----
# 非堆叠标签：label：\n value —— 逐个精确抽
LABEL_PATS = {
    "文书类型": r"文书类型：\s*\n?\s*([^\n]+)",
    "公开类型": r"公开类型：\s*\n?\s*([^\n]+)",
    "审理法院": r"审理法院：\s*\n?\s*([^\n]+)",
    "案件类型": r"案件类型：\s*\n?\s*([^\n]+)",
    "审理程序": r"审理程序：\s*\n?\s*([^\n]+)",
    "相关企业": r"相关企业：\s*\n?\s*([^\n]+)",
    "审结日期": r"审结日期：\s*\n?\s*([0-9./\-]+)",
    "审理法官": r"审理法官：\s*\n?\s*([^\n]+)",
}
# 案号：(YYYY)...号   案由：面包屑 A > B > C
CASE_NO = re.compile(r"[（(]\s*\d{4}\s*[)）][^\n，。；]{2,40}?号")
CAUSE_BREADCRUMB = re.compile(r"^\s*([^\n：]{2,12}(?:\s*>\s*[^\n：]{2,24}){1,4})\s*$", re.M)
CITE = re.compile(r"《([^》]{2,40})》第([一二三四五六七八九十百零两0-9]+)条")

# 正文噪声：法宝联想/版权/页码
BODY_CUT_MARKS = ["同案由重要案例", "下载日期", "©北大法宝", "本篇引用", "引用本篇", "原文链接"]
LABEL_LINE = re.compile(r"^\s*(案由|案\s*号|文书类型|公开类型|审理法院|案件类型|审理程序|权责关键词|相关企业)\s*：?\s*$")
NOISE_LINE = re.compile(r"^\s*(?:\d+/\d+|【法宝引证码】.*|.*人民法院认为不宜在互联网公布.*)\s*$")


def norm_date(s):
    if not s:
        return None
    m = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", s)
    return "%s-%02d-%02d" % (m.group(1), int(m.group(2)), int(m.group(3))) if m else s.strip()


def norm_law(name):
    """法规名归一：去书名号残留/空白/中华人民共和国前缀，供与图内法规名模糊比对。"""
    n = name.replace("中华人民共和国", "").replace("〈", "").replace("〉", "")
    n = n.replace("<", "").replace(">", "").replace(" ", "").strip()
    return n


def parse_meta(txt):
    m = {}
    for k, pat in LABEL_PATS.items():
        r = re.search(pat, txt)
        v = r.group(1).strip() if r else None
        # 值不能又是另一个标签
        if v and LABEL_LINE.match(v.replace("：", "：")):
            v = None
        m[k] = v
    r = CASE_NO.search(txt)
    m["案号"] = r.group(0).replace(" ", "") if r else None
    # 案由：取第一条面包屑(排除标题里的>)
    for bc in CAUSE_BREADCRUMB.findall(txt):
        if ">" in bc and "案例" not in bc:
            cause = re.sub(r"\s*>\s*", " > ", bc.strip())
            # 去尾部噪声词
            cause = re.sub(r"\s*(?:注|案由释义|案例释义|释义)\s*$", "", cause)
            cause = re.sub(r"\s*(?:注|案由释义|案例释义|释义)\s*(?=>)", "", cause)
            m["案由"] = cause.strip(" >")
            break
    m.setdefault("案由", None)
    # 年份(从案号)
    ym = re.search(r"[（(]\s*(\d{4})", m["案号"] or "")
    m["审理年份"] = ym.group(1) if ym else None
    return m


def clean_body(txt, title):
    # 起点：相关企业值之后 / 案号之后 / 首个全角缩进段，取最靠后的可用锚点
    start = 0
    for pat in (r"相关企业：\s*\n?\s*[^\n]+\n", r"[（(]\s*\d{4}\s*[)）][^\n]{2,40}?号\s*\n"):
        r = re.search(pat, txt)
        if r:
            start = max(start, r.end())
    # 终点：法宝联想/版权
    cut = len(txt)
    for mk in BODY_CUT_MARKS:
        i = txt.find(mk, start)
        if i != -1:
            cut = min(cut, i)
    body = txt[start:cut]
    title_probe = re.sub(r"\s+", "", title or "")[:20]
    kept, seen = [], set()
    for ln in body.splitlines():
        s = ln.strip()
        if not s or LABEL_LINE.match(ln) or NOISE_LINE.match(ln):
            continue
        if ">" in s:                              # 面包屑残留
            continue
        sq = re.sub(r"\s+", "", s)
        if title_probe and (sq in title_probe or title_probe in sq):   # 标题回声
            continue
        if sq in seen:                            # 非相邻重复(法宝常印多遍)
            continue
        seen.add(sq)
        kept.append(s)
    body = "\n".join(kept).strip()
    return body[:1500]                   # 摘要上限，判决书正文本就薄


def build_resolver():
    ex = json.load(open(GRAPH, encoding="utf-8"))
    art_ids = set()
    reg_by_norm = {}                     # 归一法规名 -> [law_id...]
    for n in ex["nodes"]:
        if n.get("label") == "Article":
            art_ids.add(n["id"])
        elif n.get("label") == "Regulation" and n.get("法规名"):
            key = norm_law(n["法规名"].split("·")[0])   # 去分编后缀
            reg_by_norm.setdefault(key, []).append(n["id"])
    return art_ids, reg_by_norm


GENERIC_LAW = {"条例", "办法", "规定", "规则", "细则", "规范", "标准", "通知",
               "决定", "意见", "批复", "解释", "法", "本法", "本条例", "该条例"}


def resolve_cite(law, tiao, art_ids, reg_by_norm):
    """把 (法规名,条号) 对齐到图内 Article id；命中返回 id，否则 None。
    收紧：泛指简称(《条例》《办法》等)不连，避免假阳性；含法名须≥4字或精确匹配。"""
    key = norm_law(law)
    if key in GENERIC_LAW or len(key) < 4:
        return None
    cand_laws = []
    for rk, ids in reg_by_norm.items():
        if key == rk or (len(key) >= 4 and (key in rk or rk in key)):
            cand_laws += ids
    for lid in cand_laws:
        aid = f"{lid}::第{tiao}条"
        if aid in art_ids:
            return aid
    return None


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0, help="只处理前N篇并打印解析结果(校验用)")
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    inv = json.load(open(os.path.join(PKU, "inventory_pkulaw.json"), encoding="utf-8"))
    cache = json.load(open(os.path.join(PKU, "case_text_cache.json"), encoding="utf-8"))
    cases = [r for r in inv if ".C." in (r.get("法宝引证码") or "")]
    art_ids, reg_by_norm = build_resolver()

    nodes, edges = [], []
    eseen = set()
    n_edge_cases = 0
    doctype_c, cause_c = Counter(), Counter()
    total_cites = resolved_cites = 0

    todo = cases[:args.sample] if args.sample else cases
    for c in todo:
        cli = c["法宝引证码"]
        txt = cache.get(cli)
        if not txt:
            continue
        meta = parse_meta(txt)
        body = clean_body(txt, c.get("标题"))
        # 全部援引(去重保序) + 对齐图内
        raw_cites, seen_c = [], set()
        cited_edges = []
        for law, tiao in CITE.findall(txt):
            total_cites += 1
            disp = f"《{law}》第{tiao}条"
            if disp not in seen_c:
                seen_c.add(disp); raw_cites.append(disp)
            aid = resolve_cite(law, tiao, art_ids, reg_by_norm)
            if aid:
                resolved_cites += 1
                cited_edges.append((aid, law, tiao))

        node = {
            "id": cli, "label": "Case", "标题": c.get("标题"),
            "案由": meta.get("案由"), "案号": meta.get("案号"),
            "审理法院": meta.get("审理法院"), "文书类型": meta.get("文书类型"),
            "审理程序": meta.get("审理程序"), "案件类型": meta.get("案件类型"),
            "相关企业": meta.get("相关企业"), "审理年份": meta.get("审理年份"),
            "审结日期": norm_date(meta.get("审结日期")), "审理法官": meta.get("审理法官"),
            "时效性": c.get("时效性"), "来源URL": c.get("来源URL"),
            "援引法条": raw_cites, "判决摘要": body,
        }
        nodes.append(node)
        if meta.get("文书类型"):
            doctype_c[meta["文书类型"]] += 1
        if meta.get("案由"):
            cause_c[meta["案由"]] += 1

        made = False
        for aid, law, tiao in cited_edges:
            k = (cli, aid)
            if k in eseen:
                continue
            eseen.add(k)
            edges.append({"src": cli, "rel": "援引", "dst": aid,
                          "原文法规名": law, "原文条号": f"第{tiao}条"})
            made = True
        if made:
            n_edge_cases += 1

    if args.sample:
        for nd in nodes[:args.sample]:
            print("=" * 60)
            for k in ("标题", "案由", "案号", "审理法院", "文书类型", "审理程序", "相关企业", "审理年份"):
                print(f"  {k}: {nd[k]}")
            print(f"  援引法条({len(nd['援引法条'])}):", nd["援引法条"][:6])
            print(f"  判决摘要[:120]: {nd['判决摘要'][:120]}")
        print(f"\n援引总条次 {total_cites} | 对齐图内 {resolved_cites}")
        return

    json.dump(nodes, open(os.path.join(OUT, "nodes_cases.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    json.dump(edges, open(os.path.join(OUT, "edges_cases.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    stats = {
        "Case节点": len(nodes), "援引边": len(edges),
        "有援引边的案例": n_edge_cases,
        "援引总条次": total_cites, "对齐图内条次": resolved_cites,
        "文书类型分布": dict(doctype_c.most_common()),
        "案由Top15": dict(cause_c.most_common(15)),
    }
    json.dump(stats, open(os.path.join(OUT, "stats.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"✅ Case子图：节点 {len(nodes)} | 援引边 {len(edges)}(覆盖 {n_edge_cases} 案例)")
    print(f"   援引 {total_cites} 条次，对齐图内 {resolved_cites}")
    print(f"   文书类型 {dict(doctype_c.most_common(6))}")


if __name__ == "__main__":
    main()
