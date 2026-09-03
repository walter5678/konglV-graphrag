# -*- coding: utf-8 -*-
"""
structure.py —— Phase1 文档结构化/语义分段。
把三源统一切成「条款单元」(= Article节点 = 向量库主键)，条文纯净、元数据齐全、款作内部属性。

三源（跨源按法规名去重，优先级：现有库 > dikongjie > pkulaw）：
  A. knowledge_base/raw/chunks_all.json   已结构化1680条 → 归一为单元
  B. dikongjie 29 HTML                    解析(有第X条→条; 无→语义段)
  C. pkulaw 法规(inventory keep & 类型=法规) 解析PDF头+正文→条
案例499延后(策略)。

输出：知识图谱/1_结构化/out/units_all.json + stats.json
"""
import os, sys, re, json
sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))                       # 1_结构化/
KG = os.path.dirname(HERE)                                              # 知识图谱/
BASE = os.path.dirname(KG)                                              # 项目根
KB = os.path.join(BASE, "knowledge_base")
OUT = os.path.join(HERE, "out")

sys.path.insert(0, os.path.join(KB, "scraper"))
sys.path.insert(0, os.path.join(KB, "pkulaw"))

CHUNKS_ALL = os.path.join(KB, "raw", "chunks_all.json")
DK_HTML = os.path.join(KB, "raw", "dikongjie_html")
DK_INV = os.path.join(DK_HTML, "inventory_dikongjie.json")
PKU_INV = os.path.join(KB, "pkulaw", "out", "inventory_pkulaw.json")

LONG_THRESH = 600     # 超长条阈值：拆"款"作内部属性(不另立单元)
SEG_MIN, SEG_MAX, SEG_FLOOR = 200, 600, 80  # 语义段窗口/最低字数

DRAFT_RE = re.compile(r"征求意见|草案")           # 草案/征求意见稿→跳过(用正式版)
NOISE_BODY_RE = re.compile(r"无相关内容")           # 空壳(实质在附件)


def norm_name(n):
    return re.sub(r"[（(].*?[)）]", "", n or "").strip().strip("《》 ")


def is_noise_unit(条文, 法规名):
    """丢明显噪声：空壳/标题回声/过短。保留合法短条(如施行条)。"""
    t = (条文 or "").replace("\n", "").strip()
    if NOISE_BODY_RE.search(t):
        return True
    # 去掉标题回声与纯标点后，实义内容过短→噪声
    core = t.replace(norm_name(法规名) or "\0", "")
    core = re.sub(r"[【】《》（）()，。；：、\s\d.·—-]", "", core)
    return len(core) < 8


def extract_kuan(text):
    """长条：按自然段(换行)或分号拆'款'作内部属性；短条返回None。"""
    if len(text.replace("\n", "")) < LONG_THRESH:
        return None
    parts = [p.strip() for p in text.split("\n") if p.strip()]
    if len(parts) < 2:  # 无换行的长条按分号粗分
        parts = [p.strip() for p in re.split(r"(?<=；)", text) if p.strip()]
    return parts if len(parts) > 1 else None


def make_unit(meta, 章, 节, 条号, 条文, unit_type, law_id, unit_id, source):
    return {
        "unit_id": unit_id, "law_id": law_id,
        "法规名": meta.get("法规名"), "效力层级": meta.get("效力层级"),
        "发布机关": meta.get("发布机关"), "文号": meta.get("文号"),
        "公布日期": meta.get("公布日期"), "生效日期": meta.get("生效日期"),
        "时效性": meta.get("时效性"), "来源": source,
        "章": 章, "节": 节, "条号": 条号,
        "条文": 条文.strip(), "款": extract_kuan(条文), "unit_type": unit_type,
    }


def semantic_segments(body_lines):
    """无第X条结构：按自然段贪心并到200-600字窗口。"""
    segs, buf = [], ""
    for ln in body_lines:
        ln = ln.strip()
        if not ln:
            continue
        if len(buf) + len(ln) <= SEG_MAX or not buf:
            buf = (buf + "\n" + ln) if buf else ln
        else:
            segs.append(buf); buf = ln
        if len(buf) >= SEG_MIN:
            segs.append(buf); buf = ""
    if buf.strip():
        if segs and len(buf) < SEG_FLOOR:
            segs[-1] += "\n" + buf
        else:
            segs.append(buf)
    return [s for s in segs if len(s.replace("\n", "")) >= SEG_FLOOR]


# ========== A. 现有 chunks_all ==========
def load_existing(seen):
    units = []
    data = json.load(open(CHUNKS_ALL, encoding="utf-8"))
    for c in data:
        cid = c.get("chunk_id") or ""
        law_id = cid.split("::")[0] if "::" in cid else norm_name(c.get("法规名"))
        meta = {k: c.get(k) for k in ("法规名", "效力层级", "发布机关", "文号",
                                      "公布日期", "生效日期", "时效性")}
        units.append(make_unit(meta, c.get("章"), c.get("节"), c.get("条号"),
                                c.get("条文") or "", "条", law_id, cid, "existing"))
        seen.add(norm_name(c.get("法规名")))
    return units


# ========== B. dikongjie ==========
def load_dikongjie(seen):
    from fetch_dikongjie import extract_body, parse_articles
    units, added = [], 0
    inv = json.load(open(DK_INV, encoding="utf-8"))
    for r in inv:
        if r.get("状态") not in ("待chunk", "待定"):
            continue
        key = norm_name(r.get("标题"))
        if key in seen or DRAFT_RE.search(r.get("标题") or ""):
            continue
        path = os.path.join(KB, os.path.relpath(r["文件路径"]))
        path = os.path.join(KB, r["文件路径"]) if not os.path.isabs(r["文件路径"]) else r["文件路径"]
        if not os.path.exists(path):
            continue
        html = open(path, encoding="utf-8").read()
        body, date = extract_body(html)
        law_id = f"dikongjie_{r['id']}"
        meta = {"法规名": r["标题"], "效力层级": r.get("效力层级"),
                "发布机关": r.get("地区") or "地方", "文号": "",
                "公布日期": r.get("发布日期") or date, "生效日期": "",
                "时效性": "送审稿/未生效" if r.get("状态") == "待定" else "有效"}
        arts = parse_articles(body, mode="条")
        if arts:
            for a in arts:
                t = (a.get("条文") or "").strip()
                if len(t.replace("\n", "")) < 8:
                    continue
                units.append(make_unit(meta, a.get("章"), a.get("节"), a.get("条号"),
                                       t, "条", law_id, f"{law_id}::{a.get('条号')}", "dikongjie"))
        else:
            for i, seg in enumerate(semantic_segments(body), 1):
                units.append(make_unit(meta, None, None, f"段{i}", seg, "语义段",
                                       law_id, f"{law_id}::段{i}", "dikongjie"))
        seen.add(key); added += 1
    return units, added


# ========== C. pkulaw 法规 ==========
def load_pkulaw(seen):
    from parse_pkulaw import process_pdf, split_articles
    units, added, failed = [], 0, 0
    inv = json.load(open(PKU_INV, encoding="utf-8"))
    for r in inv:
        if not (r.get("keep") and r.get("类型") == "法规"):
            continue
        key = norm_name(r.get("标题"))
        if key in seen or not key or DRAFT_RE.search(r.get("标题") or ""):
            continue
        rel = r.get("文件路径")
        path = os.path.join(KB, rel) if rel and not os.path.isabs(rel) else rel
        if not path or not os.path.exists(path):
            continue
        try:
            meta, body, keep, reason = process_pdf(path)
            if not keep:
                continue
            law_id = meta.get("法宝引证码") or key
            for a in split_articles(body):
                t = (a.get("条文") or "").strip()
                if len(t.replace("\n", "")) < 8:
                    continue
                tiao = a.get("条号") or "全文"
                utype = "条" if a.get("条号") else "全文"
                units.append(make_unit(meta, a.get("章"), a.get("节"), a.get("条号"),
                                       t, utype, law_id, f"{law_id}::{tiao}", "pkulaw"))
            seen.add(key); added += 1
        except Exception as e:
            failed += 1
    return units, added, failed


def main():
    import argparse
    ap = argparse.ArgumentParser()
    # dikongjie/pkulaw 现已并入 chunks_all(严筛版)，默认只走 A 源避免 B/C 用旧筛选逻辑
    # 重新引入被严筛剔除的数据；--rescan 恢复旧的三源解析行为。
    ap.add_argument("--rescan", action="store_true",
                    help="额外走 B/C 独立解析 dikongjie/pkulaw(旧行为，chunks_all 未含时用)")
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    seen = set()
    print("A. 归一现有 chunks_all ...")
    u_exist = load_existing(seen)
    print(f"   {len(u_exist)} 单元 / {len(seen)} 部法规")

    u_dk, n_dk, u_pku, n_pku, fail = [], 0, [], 0, 0
    if args.rescan:
        print("B. 结构化 dikongjie ...")
        u_dk, n_dk = load_dikongjie(seen)
        print(f"   +{len(u_dk)} 单元 / {n_dk} 部")

        print("C. 结构化 pkulaw 法规 ...")
        u_pku, n_pku, fail = load_pkulaw(seen)
        print(f"   +{len(u_pku)} 单元 / {n_pku} 部（解析失败 {fail}）")
    else:
        print("B/C 跳过(dikongjie/pkulaw 已在 chunks_all 严筛版中；如需重新解析加 --rescan)")

    units_raw = u_exist + u_dk + u_pku
    units = [u for u in units_raw if not is_noise_unit(u["条文"], u["法规名"])]
    n_drop = len(units_raw) - len(units)
    print(f"\n清理噪声单元(空壳/标题回声/过短): 丢弃 {n_drop}")
    json.dump(units, open(os.path.join(OUT, "units_all.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    # 统计
    by_src, by_type, n_long = {}, {}, 0
    laws = set()
    for u in units:
        by_src[u["来源"]] = by_src.get(u["来源"], 0) + 1
        by_type[u["unit_type"]] = by_type.get(u["unit_type"], 0) + 1
        laws.add(u["law_id"])
        if u["款"]:
            n_long += 1
    stats = {"单元总数": len(units), "法规数": len(laws), "按来源": by_src,
             "按类型": by_type, "含款拆分的长条": n_long}
    json.dump(stats, open(os.path.join(OUT, "stats.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n✅ units_all.json：{len(units)} 单元 / {len(laws)} 部法规")
    print(f"   来源 {by_src}")
    print(f"   类型 {by_type}｜含款长条 {n_long}")


if __name__ == "__main__":
    main()
