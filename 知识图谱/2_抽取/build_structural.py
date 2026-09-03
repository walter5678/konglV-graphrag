# -*- coding: utf-8 -*-
"""
build_structural.py —— 步骤②：结构骨架（免LLM，元数据直接建，高置信）。
从 units_normalized.json 建：
  节点：Regulation(法规) / Section(章,可选节) / Article(条款=单元)
  边：  Article──属于──►Section──属于──►Regulation  (无章时 Article 直接挂 Regulation)
输出 out/nodes_structural.json + edges_structural.json
"""
import os, sys, json
sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
IN = os.path.join(os.path.dirname(HERE), "1_结构化", "out", "units_normalized.json")
OUT = os.path.join(HERE, "out")


def main():
    os.makedirs(OUT, exist_ok=True)
    units = json.load(open(IN, encoding="utf-8"))

    regs, secs, arts, edges = {}, {}, [], []
    for u in units:
        lid = u["law_id"]
        # 法规节点（取该法规首次出现的元数据）
        if lid not in regs:
            regs[lid] = {
                "id": lid, "type": "Regulation", "法规名": u.get("法规名"),
                "效力层级": u.get("效力层级"), "效力rank": u.get("效力rank"),
                "时效性": u.get("时效性"), "版本注记": u.get("版本注记"),
                "发布机关": u.get("发布机关"), "文号": u.get("文号"),
                "公布日期": u.get("公布日期"), "生效日期": u.get("生效日期"), "来源": u.get("来源"),
            }
        # 章节点（可选）
        parent = lid
        章 = (u.get("章") or "").strip()
        if 章:
            sid = f"{lid}::{章}"
            if sid not in secs:
                secs[sid] = {"id": sid, "type": "Section", "标题": 章, "law_id": lid}
                edges.append({"src": sid, "rel": "属于", "dst": lid})  # 章→法规
            parent = sid
        # 条款节点
        arts.append({
            "id": u["unit_id"], "type": "Article", "law_id": lid,
            "条号": u.get("条号"), "unit_type": u.get("unit_type"),
            "章": 章 or None, "节": u.get("节"),
            "效力层级": u.get("效力层级"), "时效性": u.get("时效性"),
        })
        edges.append({"src": u["unit_id"], "rel": "属于", "dst": parent})  # 条→章/法规

    nodes = {"Regulation": list(regs.values()), "Section": list(secs.values()),
             "Article": arts}
    json.dump(nodes, open(os.path.join(OUT, "nodes_structural.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    json.dump(edges, open(os.path.join(OUT, "edges_structural.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print("✅ 结构骨架已建")
    print(f"   节点：Regulation {len(regs)} ｜ Section {len(secs)} ｜ Article {len(arts)}")
    print(f"   边(属于)：{len(edges)}")
    # 时效/层级视角小结（骨架即可回答的问题基础）
    from collections import Counter
    print(f"   法规时效性：{dict(Counter(r['时效性'] for r in regs.values()))}")
    print(f"   法规效力层级：{dict(Counter(r['效力层级'] for r in regs.values()))}")


if __name__ == "__main__":
    main()
