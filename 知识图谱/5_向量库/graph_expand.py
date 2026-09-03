# -*- coding: utf-8 -*-
"""
graph_expand.py —— GraphRAG 图多跳扩展：以向量召回的种子法条为入口，
沿 Neo4j 图边找结构相关的其他条款(纯向量召回会漏的)。

精选边策略(与用户确认)：
  ① 引用 双向 1 跳(A 依照 B / B 依照 A)
  ② 经共享实体 1 跳：种子 -[适用于/定义/义务主体]-> 实体 <-[同边]- 其他条款
     (同机型/场景、同术语、同义务主体的条款)
不用「违反后果/同章」(噪声)。

图 schema：节点 (:Article:Entity {id})，Article.id == 向量库 parent_id(unit_id)。
关系类型是中文，Cypher 里用反引号转义：`引用`/`适用于`/`定义`/`义务主体`。
条文直接取自图节点 `条文` 属性，图扩展自成闭环，不依赖向量库。

连接：环境变量 NEO4J_URI(默认 bolt://localhost:7687)/NEO4J_USER(默认 neo4j)/NEO4J_PASSWORD。

自测：python graph_expand.py --ping
"""
import os, sys, argparse, math
from collections import defaultdict
sys.stdout.reconfigure(encoding="utf-8")

DEFAULT_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
DEFAULT_USER = os.environ.get("NEO4J_USER", "neo4j")

REF_WEIGHT = 3.0   # 引用边固定高权重(直接法条引用,强相关)

_EXPAND_CYPHER = """
UNWIND $seeds AS sid
MATCH (s:Article:Entity {id: sid})
OPTIONAL MATCH (s)-[:`引用`]-(r1:Article)
OPTIONAL MATCH (s)-[e:`适用于`|`定义`|`义务主体`]->(x)<-[:`适用于`|`定义`|`义务主体`]-(r2:Article)
WITH sid,
  collect(DISTINCT {nid:r1.id, via:'引用', ent:null, 法规名:r1.法规名, 条号:r1.条号, 条文:r1.条文, 时效性:r1.时效性}) AS refs,
  collect(DISTINCT {nid:r2.id, via:type(e)+'·共享「'+coalesce(x.id,'')+'」', ent:x.id, 法规名:r2.法规名, 条号:r2.条号, 条文:r2.条文, 时效性:r2.时效性}) AS shares
UNWIND (refs + shares) AS nb
WITH sid, nb WHERE nb.nid IS NOT NULL
RETURN sid AS sid, nb.nid AS nid, nb.via AS via, nb.ent AS ent,
       nb.法规名 AS 法规名, nb.条号 AS 条号, nb.条文 AS 条文, nb.时效性 AS 时效性
"""

# 共享实体的度(经 适用于/定义/义务主体 连接的 Article 数)——用于稀有度降权
_DEG_CYPHER = """
MATCH (x)<-[:`适用于`|`定义`|`义务主体`]-(:Article)
RETURN x.id AS eid, count(*) AS deg
"""


class GraphExpander:
    def __init__(self, uri=None, user=None, pwd=None):
        from neo4j import GraphDatabase
        uri = uri or DEFAULT_URI
        user = user or DEFAULT_USER
        pwd = pwd or os.environ.get("NEO4J_PASSWORD")
        if not pwd:
            raise RuntimeError("未提供 NEO4J_PASSWORD(环境变量或 --pwd)")
        self.driver = GraphDatabase.driver(uri, auth=(user, pwd))
        self._entity_deg = None      # 懒加载：实体 id -> 度

    def close(self):
        self.driver.close()

    def _load_entity_deg(self):
        """一次性载入各共享实体的度，供稀有度加权。"""
        if self._entity_deg is None:
            with self.driver.session() as s:
                self._entity_deg = {r["eid"]: r["deg"] for r in s.run(_DEG_CYPHER)}
        return self._entity_deg

    def _via_weight(self, via, ent, deg):
        """边权：引用边高固定权重；共享实体边按稀有度 1/log2(2+deg)(高频机型/主体降权)。"""
        if via == "引用" or ent is None:
            return REF_WEIGHT
        d = deg.get(ent, 1)
        return 1.0 / math.log2(2 + d)

    def ping(self):
        with self.driver.session() as s:
            nodes = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
            rels = s.run("MATCH ()-[r]->() RETURN type(r) AS t, count(r) AS c "
                         "ORDER BY c DESC").data()
        return nodes, rels

    def expand(self, seed_ids, only_current=True, per_seed=5, max_total=20):
        """seed_ids=向量召回的 Article id 列表 → 结构相关的关联条款(带溯源)。
        排序键=稀有度加权分(引用边高权、经高频实体的共享边降权)，而非单纯命中种子数。"""
        seed_set = set(seed_ids)
        deg = self._load_entity_deg()
        agg = {}                       # nid -> 邻居聚合
        by_seed = defaultdict(list)    # sid -> [nid...]
        with self.driver.session() as s:
            for rec in s.run(_EXPAND_CYPHER, seeds=list(seed_ids)):
                nid = rec["nid"]
                if not nid or nid in seed_set:      # 剔空 / 剔种子自身
                    continue
                if only_current and (rec["时效性"] or "") != "现行有效":
                    continue
                d = agg.setdefault(nid, {
                    "id": nid, "法规名": rec["法规名"], "条号": rec["条号"],
                    "条文": rec["条文"], "时效性": rec["时效性"],
                    "vias": set(), "from_seeds": set(), "score": 0.0})
                d["vias"].add(rec["via"])
                d["from_seeds"].add(rec["sid"])
                d["score"] += self._via_weight(rec["via"], rec["ent"], deg)
                by_seed[rec["sid"]].append(nid)

        # 每种子保留加权分最高的 per_seed 个邻居 → 并集为候选
        keep = set()
        for sid, nids in by_seed.items():
            uniq = list(dict.fromkeys(nids))
            uniq.sort(key=lambda n: agg[n]["score"], reverse=True)
            keep.update(uniq[:per_seed])
        cand = [agg[n] for n in keep]
        # 加权分高者排前(引用边/稀有共享实体优先，高频机型共享被压低)
        cand.sort(key=lambda d: d["score"], reverse=True)
        for d in cand:
            d["vias"] = sorted(d["vias"])
            d["from_seeds"] = sorted(d["from_seeds"])
        return cand[:max_total]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ping", action="store_true")
    ap.add_argument("--pwd")
    args = ap.parse_args()
    ge = GraphExpander(pwd=args.pwd)
    try:
        if args.ping:
            nodes, rels = ge.ping()
            print(f"✅ 已连接 {DEFAULT_URI} | 节点 {nodes}")
            total = sum(r["c"] for r in rels)
            for r in rels:
                print(f"   [{r['t']}] {r['c']}")
            print(f"   关系合计 {total}")
    finally:
        ge.close()


if __name__ == "__main__":
    main()
