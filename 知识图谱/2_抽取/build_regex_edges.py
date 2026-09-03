# -*- coding: utf-8 -*-
"""
build_regex_edges.py —— 步骤③：正则抽高置信边。
  引用 REFERENCES：条文里 第X条 / 《法规名》第X条
     · 同法规 → 指向 本law_id::第X条（校验该条存在）
     · 跨法规 → 按法规名索引解析 law_id，解析不到记 unresolved
  定义 DEFINES：  "XX，是指…" / "所称XX，是指" → Term节点 + 定义边
输出 out/edges_references.json / edges_defines.json / nodes_term.json
"""
import os, sys, re, json
sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
IN = os.path.join(os.path.dirname(HERE), "1_结构化", "out", "units_normalized.json")
OUT = os.path.join(HERE, "out")

CN = "一二三四五六七八九十百零两0-9"
RE_CROSS = re.compile(r"《([^》]{2,40})》\s*第([%s]+)条" % CN)      # 《法规名》第X条
RE_TIAO = re.compile(r"第([%s]+)条" % CN)                          # 第X条
RE_DEF1 = re.compile(r"所称([^，。；：]{2,20})[，,]\s*是指")
RE_DEF2 = re.compile(r"([一-龥A-Za-z]{2,20})[，,]\s*是指")


def norm_name(n):
    return re.sub(r"[（(].*?[)）]", "", n or "").strip().strip("《》 ")


def main():
    os.makedirs(OUT, exist_ok=True)
    units = json.load(open(IN, encoding="utf-8"))

    # 索引：法规名 → law_id；(law_id,条号) 存在集合
    name2lid, exist = {}, set()
    for u in units:
        name2lid.setdefault(norm_name(u.get("法规名")), u["law_id"])
        if u.get("条号"):
            exist.add((u["law_id"], u["条号"]))

    def resolve_name(raw):
        k = norm_name(raw)
        if k in name2lid:
            return name2lid[k]
        for nm, lid in name2lid.items():   # 宽松包含匹配
            if k and (k in nm or nm in k):
                return lid
        return None

    refs, defs, terms, unresolved = [], [], {}, 0
    for u in units:
        text, lid, self_tiao = u.get("条文") or "", u["law_id"], u.get("条号")
        # --- 跨法规引用（先抽，抽完从文本移除避免被同法规规则重复计）---
        consumed = []
        for m in RE_CROSS.finditer(text):
            law_raw, tiao = m.group(1), "第" + m.group(2) + "条"
            tgt = resolve_name(law_raw)
            if tgt:
                refs.append({"src": u["unit_id"], "rel": "引用", "dst": f"{tgt}::{tiao}",
                             "跨法规": True, "目标法规名": norm_name(law_raw)})
            else:
                refs.append({"src": u["unit_id"], "rel": "引用", "dst": None,
                             "跨法规": True, "目标法规名": norm_name(law_raw),
                             "目标条号": tiao, "status": "unresolved"})
                unresolved += 1
            consumed.append(m.span())
        # 移除已消费区间
        masked = text
        for s, e in reversed(consumed):
            masked = masked[:s] + "　" * (e - s) + masked[e:]
        # --- 同法规引用 ---
        for m in RE_TIAO.finditer(masked):
            tiao = "第" + m.group(1) + "条"
            if tiao == self_tiao:                     # 跳过自引
                continue
            if (lid, tiao) in exist:
                refs.append({"src": u["unit_id"], "rel": "引用", "dst": f"{lid}::{tiao}",
                             "跨法规": False})
        # --- 定义 ---
        hit_def_src = False
        for m in RE_DEF1.finditer(text):
            term = m.group(1).strip()
            if len(term) >= 2:
                terms.setdefault(term, {"id": term, "type": "Term", "术语名": term})
                defs.append({"src": u["unit_id"], "rel": "定义", "dst": term})
                hit_def_src = True
        if not hit_def_src:                            # 无"所称"才用宽松规则
            for m in RE_DEF2.finditer(text):
                term = m.group(1).strip()
                if len(term) < 2 or term.startswith("是指"):
                    continue
                terms.setdefault(term, {"id": term, "type": "Term", "术语名": term})
                defs.append({"src": u["unit_id"], "rel": "定义", "dst": term})

    # 去重
    def dedup(lst):
        seen, out = set(), []
        for e in lst:
            k = (e["src"], e.get("dst"), e.get("目标法规名"), e.get("目标条号"))
            if k in seen:
                continue
            seen.add(k); out.append(e)
        return out
    refs, defs = dedup(refs), dedup(defs)

    json.dump(refs, open(os.path.join(OUT, "edges_references.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump(defs, open(os.path.join(OUT, "edges_defines.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump(list(terms.values()), open(os.path.join(OUT, "nodes_term.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    same = sum(1 for r in refs if not r.get("跨法规"))
    cross_ok = sum(1 for r in refs if r.get("跨法规") and r.get("dst"))
    print("✅ 正则抽边完成")
    print(f"   引用 REFERENCES：{len(refs)}（同法规 {same}｜跨法规解析成功 {cross_ok}｜跨法规未解析 {unresolved}）")
    print(f"   定义 DEFINES：{len(defs)} 边 / 术语节点 {len(terms)}")


if __name__ == "__main__":
    main()
