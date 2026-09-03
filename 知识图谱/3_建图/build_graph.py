# -*- coding: utf-8 -*-
"""
build_graph.py —— Phase3：把三类边合并成完整知识图谱并导出。
输入（2_抽取/out/ 与 1_结构化/out/）：
  units_normalized.json           Article 条文/元数据
  nodes_structural.json / edges_structural.json   法规/章/条 + 属于
  edges_references.json / edges_defines.json / nodes_term.json   引用/定义/术语(正则)
  nodes_llm.json / edges_llm.json （可选,LLM抽完才有）术语/机型/主体/场景/罚则 + 适用于/义务主体/违反后果
含步骤⑤归一：实体id过 vocab.canon 合并别名。
输出（3_建图/out/）：graph_export.json（统一节点/边）、neo4j_import.cypher、stats.json
"""
import os, sys, json
from collections import Counter, defaultdict
sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
KG = os.path.dirname(HERE)
EX = os.path.join(KG, "2_抽取", "out")
ST = os.path.join(KG, "1_结构化", "out")
CA = os.path.join(KG, "4_案例", "out")
OUT = os.path.join(HERE, "out")
sys.path.insert(0, os.path.join(KG, "2_抽取"))
from vocab import canon


def load(path, default):
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else default


def main():
    os.makedirs(OUT, exist_ok=True)
    units = {u["unit_id"]: u for u in load(os.path.join(ST, "units_normalized.json"), [])}
    nstruct = load(os.path.join(EX, "nodes_structural.json"), {})
    estruct = load(os.path.join(EX, "edges_structural.json"), [])
    erefs = load(os.path.join(EX, "edges_references.json"), [])
    edefs = load(os.path.join(EX, "edges_defines.json"), [])
    nterm = load(os.path.join(EX, "nodes_term.json"), [])
    nllm = load(os.path.join(EX, "nodes_llm.json"), {})
    ellm = load(os.path.join(EX, "edges_llm.json"), [])
    ncases = load(os.path.join(CA, "nodes_cases.json"), [])
    ecases = load(os.path.join(CA, "edges_cases.json"), [])

    nodes = {}   # id -> {id,label,props}
    def add_node(nid, label, **props):
        if not nid:
            return
        if nid not in nodes:
            nodes[nid] = {"id": nid, "label": label, **{k: v for k, v in props.items() if v is not None}}

    # --- 结构节点 ---
    for r in nstruct.get("Regulation", []):
        add_node(r["id"], "Regulation", **{k: r.get(k) for k in
                 ("法规名", "效力层级", "效力rank", "时效性", "版本注记", "发布机关", "文号", "公布日期", "生效日期")})
    for s in nstruct.get("Section", []):
        add_node(s["id"], "Section", 标题=s.get("标题"), law_id=s.get("law_id"))
    for a in nstruct.get("Article", []):
        u = units.get(a["id"], {})
        add_node(a["id"], "Article", law_id=a.get("law_id"), 条号=a.get("条号"),
                 unit_type=a.get("unit_type"), 效力层级=a.get("效力层级"), 时效性=a.get("时效性"),
                 法规名=u.get("法规名"), 条文=u.get("条文"))
    # --- 实体节点（术语/机型/主体/场景/罚则），过 canon 归一 ---
    # 机型优先：canon 后仍属 DroneCategory 的 id 不再被 Term 抢占 label
    # (add_node 首个 label 生效；同名概念既被抽成 Term 又被抽成机型时，机型是更准的 label)
    dc_ids = {c for c in (canon(d["id"]) for d in nllm.get("DroneCategory", [])) if c}
    for t in nterm:
        if canon(t["术语名"]) in dc_ids:
            continue
        add_node(canon(t["术语名"]), "Term", 术语名=canon(t["术语名"]))
    for t in nllm.get("Term", []):
        if canon(t["id"]) in dc_ids:
            continue
        add_node(canon(t["id"]), "Term", 术语名=canon(t["id"]), 定义=t.get("定义"))
    for d in nllm.get("DroneCategory", []):
        add_node(canon(d["id"]), "DroneCategory")
    for a in nllm.get("Actor", []):
        add_node(canon(a["id"]), "Actor")
    for a in nllm.get("Activity", []):
        add_node(canon(a["id"]), "Activity")
    for s in nllm.get("Sanction", []):
        add_node(s["id"], "Sanction", **{k: v for k, v in s.items() if k != "id"})
    # --- 案例节点 ---
    for c in ncases:
        add_node(c["id"], "Case", **{k: v for k, v in c.items() if k not in ("id", "label")})

    # --- 边（去重）---
    edges, eseen = [], set()
    def add_edge(src, rel, dst, **props):
        if not src or not dst:
            return
        k = (src, rel, dst)
        if k in eseen:
            return
        eseen.add(k); edges.append({"src": src, "rel": rel, "dst": dst, **props})

    for e in estruct:
        add_edge(e["src"], "属于", e["dst"])
    for e in erefs:
        if e.get("dst"):
            add_edge(e["src"], "引用", e["dst"], 跨法规=e.get("跨法规", False))
    for e in edefs:
        add_edge(e["src"], "定义", canon(e["dst"]))
    for e in ellm:
        rel = e["rel"]
        dst = canon(e["dst"]) if rel in ("定义", "适用于", "义务主体") else e["dst"]
        add_edge(e["src"], rel, dst, **{k: v for k, v in e.items() if k not in ("src", "rel", "dst")})
    for e in ecases:
        add_edge(e["src"], e["rel"], e["dst"], **{k: v for k, v in e.items() if k not in ("src", "rel", "dst")})

    # --- 导出 JSON ---
    export = {"nodes": list(nodes.values()), "edges": edges}
    json.dump(export, open(os.path.join(OUT, "graph_export.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    # --- 导出 Neo4j Cypher ---
    # 规范写法：①每类标签建 id 唯一约束(自带索引) + 公共标签 :Entity 供边快速匹配
    #          ②节点按 id MERGE 再 SET 属性(可重入,不拿长条文当匹配键)
    #          ③边用 :Entity(id) 索引匹配,避免全表扫
    def esc(v):
        return str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")

    def cval(v):
        """Cypher 属性值：list→字符串数组字面量，其余→带引号字符串。"""
        if isinstance(v, list):
            return "[" + ", ".join(f'"{esc(x)}"' for x in v) + "]"
        return f'"{esc(v)}"'

    labels = sorted({n["label"] for n in nodes.values()})
    with open(os.path.join(OUT, "neo4j_import.cypher"), "w", encoding="utf-8") as f:
        f.write("// === 约束/索引(先建,保证导入快且可重入) ===\n")
        f.write("CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE;\n")
        for lab in labels:
            f.write(f"CREATE INDEX {lab.lower()}_id IF NOT EXISTS FOR (n:{lab}) ON (n.id);\n")
        f.write("\n// === 节点 ===\n")
        for n in nodes.values():
            props = ", ".join(f'{k}: {cval(v)}' for k, v in n.items() if k != "label")
            # 同时打 :Entity 公共标签,供边匹配走全局 id 索引
            f.write(f'MERGE (n:{n["label"]}:Entity {{id: "{esc(n["id"])}"}}) SET n += {{{props}}};\n')
        f.write("\n// === 边 ===\n")
        for e in edges:
            eprops = {k: v for k, v in e.items() if k not in ("src", "rel", "dst")}
            setp = ""
            if eprops:
                setp = " SET r += {" + ", ".join(f'{k}: {cval(v)}' for k, v in eprops.items()) + "}"
            f.write(f'MATCH (a:Entity {{id:"{esc(e["src"])}"}}),(b:Entity {{id:"{esc(e["dst"])}"}}) '
                    f'MERGE (a)-[r:{e["rel"]}]->(b){setp};\n')

    # --- 统计 ---
    nlab = Counter(n["label"] for n in nodes.values())
    erel = Counter(e["rel"] for e in edges)
    stats = {"节点总数": len(nodes), "边总数": len(edges),
             "节点按类型": dict(nlab), "边按类型": dict(erel)}
    json.dump(stats, open(os.path.join(OUT, "stats.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("✅ 图谱已构建并导出")
    print(f"   节点 {len(nodes)}：{dict(nlab)}")
    print(f"   边   {len(edges)}：{dict(erel)}")

    # --- 可选 networkx 统计 ---
    try:
        import networkx as nx
        G = nx.MultiDiGraph()
        for n in nodes.values():
            G.add_node(n["id"], **{k: v for k, v in n.items() if k != "id"})
        for e in edges:
            G.add_edge(e["src"], e["dst"], key=e["rel"])
        nx.write_graphml(G, os.path.join(OUT, "graph.graphml"))
        deg = sorted(G.degree, key=lambda x: -x[1])[:8]
        print(f"   graphml 已导出；度最高节点: {[(nodes[i]['label'], nodes[i].get('法规名') or nodes[i].get('术语名') or i, d) for i, d in deg]}")
    except ImportError:
        print("   (未装 networkx，跳过 graphml；graph_export.json + cypher 已足够)")


if __name__ == "__main__":
    main()
