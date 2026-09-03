# -*- coding: utf-8 -*-
"""
search.py —— hybrid 混合召回入口：BM25 稀疏 + BGE-M3 稠密，RRF 融合。

两路召回在 child 层融合，再按 parent_id 回溯父块全文(沿用父子分块)。
- 稠密：build_vectordb 的 Chroma 向量检索(复用 get_client/embed_batch/_resolve_db)。
- 稀疏：build_bm25 建的 out/bm25.pkl(jieba+领域词典)。
- 融合：RRF(Reciprocal Rank Fusion, k=60)，量纲无关，--alpha 调稠密权重。

用法：
  set SILICONFLOW_API_KEY=sk-xxx
  python search.py --query "微型无人机最大起飞重量" --mode hybrid --only-current
  python search.py --query "适航审定" --mode dense    # 对比
  python search.py --query "适航审定" --mode sparse   # 纯 BM25(无需 key)
"""
import os, sys, json, pickle, argparse
import urllib.request, urllib.error
from functools import lru_cache
sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "out")
BM25_PKL = os.path.join(OUT, "bm25.pkl")
PARENTS = os.path.join(OUT, "parents.json")

import build_vectordb as bv   # 复用 get_client / embed_batch / _resolve_db / DB / COLL

RRF_K = 60
RERANK_URL = os.environ.get("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1").rstrip("/") + "/rerank"
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"


def get_key(key):
    key = key or os.environ.get("SILICONFLOW_API_KEY")
    if not key:
        sys.exit("✗ rerank/dense 需要 API key：set SILICONFLOW_API_KEY 或传 --key")
    return key


def do_rerank(query, cand, model, key, top_n):
    """cross-encoder 精排：对 cand=[(cid, info)] 用 info['snip'] 作文档调 rerank API，
    返回按 relevance_score 降序的 [(cid, info)](info['score'] 换成 rerank 分)。"""
    docs = [((info.get("snip") or info["meta"].get("法规名") or "")[:1500]) for _, info in cand]
    body = json.dumps({"model": model, "query": query, "documents": docs,
                       "top_n": top_n, "return_documents": False}).encode("utf-8")
    req = urllib.request.Request(RERANK_URL, data=body, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    res = json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))
    out = []
    for r in res["results"]:
        cid, info = cand[r["index"]]
        info = dict(info)
        info["score"] = r["relevance_score"]
        out.append((cid, info))
    return out


@lru_cache(maxsize=1)
def load_bm25():
    """BM25 索引(缓存：web 常驻服务下只 load 一次)。"""
    with open(BM25_PKL, "rb") as f:
        return pickle.load(f)


@lru_cache(maxsize=1)
def load_parents():
    """parent 全文边车(缓存)。"""
    return json.load(open(PARENTS, encoding="utf-8"))


@lru_cache(maxsize=1)
def get_collection():
    """Chroma collection(缓存：避免每请求重开 PersistentClient)。"""
    import chromadb
    return chromadb.PersistentClient(path=bv.DB).get_collection(bv.COLL)


def meta_pass(meta, only_current):
    return not (only_current and meta.get("时效性") != "现行有效")


def dense_rank(client, query, cand, only_current):
    """→ [(child_id, meta, sim, snippet)] 按相似度降序。"""
    coll = get_collection()
    qvec = bv.embed_batch(client, [query])[0]
    where = {"时效性": "现行有效"} if only_current else None
    res = coll.query(query_embeddings=[qvec], n_results=cand, where=where,
                     include=["metadatas", "distances", "documents"])
    return [(cid, meta, 1 - dist, doc) for cid, meta, dist, doc
            in zip(res["ids"][0], res["metadatas"][0],
                   res["distances"][0], res["documents"][0])]


def sparse_rank(store, query, cand, only_current):
    """→ [(child_id, meta, bm25分, snippet)] 按 BM25 分降序(仅 >0)。"""
    from build_bm25 import tokenize
    scores = store["bm25"].get_scores(tokenize(query))
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    out = []
    for i in order:
        if scores[i] <= 0:
            break
        meta = store["metas"][i]
        if not meta_pass(meta, only_current):
            continue
        out.append((store["child_ids"][i], meta, float(scores[i]), store["raws"][i]))
        if len(out) >= cand:
            break
    return out


def rrf_fuse(dense, sparse, alpha, k=RRF_K):
    """RRF：score(id)=Σ weight/(k+rank)。alpha=稠密权重,稀疏=1-alpha。"""
    fused = {}
    for rank, (cid, meta, _s, snip) in enumerate(dense):
        fused.setdefault(cid, {"meta": meta, "score": 0.0, "snip": snip})
        fused[cid]["score"] += alpha / (k + rank + 1)
    for rank, (cid, meta, _s, snip) in enumerate(sparse):
        d = fused.setdefault(cid, {"meta": meta, "score": 0.0, "snip": snip})
        d["score"] += (1 - alpha) / (k + rank + 1)
    return sorted(fused.items(), key=lambda kv: kv[1]["score"], reverse=True)


def to_ranked(triples):
    """单路结果转成与 rrf_fuse 一致的 [(cid, {meta,score,snip})]。"""
    return [(cid, {"meta": meta, "score": s, "snip": snip})
            for cid, meta, s, snip in triples]


def emit_expansion(args, seeds, seed_label):
    """分层输出：图多跳扩展出的关联条款,带溯源。连接/依赖失败则优雅降级。"""
    nbrs, err = expand_seeds(args, seeds)
    if err:
        print(f"\n⚠ {err}")
        return

    print(f"\n── 🔗 关联条款(图扩展 · {len(nbrs)}条) " + "─" * 28)
    if not nbrs:
        print("  (无结构相关条款)")
        return
    for d in nbrs:
        srcs = "、".join(seed_label.get(s, s) for s in d["from_seeds"][:2])
        vias = "，".join(d["vias"][:2])
        flag = "" if d.get("时效性") == "现行有效" else f"[{d.get('时效性')}]"
        hit = f"×{len(d['from_seeds'])}种子" if len(d["from_seeds"]) > 1 else ""
        print(f"\n● {flag}《{d.get('法规名')}》{d.get('条号') or ''} {hit}")
        print(f"  ↳溯源: 经 {srcs} 的[{vias}]")
        print(f"  {(d.get('条文') or '')[:110]}")


def expand_seeds(args, seeds):
    """图多跳扩展 → 关联条款列表。失败返回 ([], 告警字符串)，成功返回 (nbrs, None)。"""
    try:
        from graph_expand import GraphExpander
        ge = GraphExpander(pwd=args.neo4j_pwd)
    except Exception as e:
        return [], f"图扩展跳过(Neo4j 连接/依赖失败): {str(e)[:100]}"
    try:
        nbrs = ge.expand(seeds, only_current=args.only_current,
                         per_seed=args.expand_per, max_total=args.expand_max)
        return nbrs, None
    except Exception as e:
        return [], f"图扩展查询失败: {str(e)[:100]}"
    finally:
        ge.close()


def retrieve(args):
    """完整检索链 → 结构化结果(供 CLI 打印与问答生成复用)。
    返回 {query, mode, reranked, only_current, alpha, hits[], seed_label{}, expansion[]}。
    hits 每项: {score, 法规名, 条号, node_type, 时效性, parent_id, head, is_article,
                child, parent_text(首次出现该 parent 时为全文,否则 None)}。"""
    parents = load_parents()
    dense, sparse = [], []
    if args.mode in ("dense", "hybrid"):
        client = bv.get_client(args.key)
        dense = dense_rank(client, args.query, args.cand, args.only_current)
    if args.mode in ("sparse", "hybrid"):
        sparse = sparse_rank(load_bm25(), args.query, args.cand, args.only_current)

    if args.mode == "dense":
        ranked = to_ranked(dense)
    elif args.mode == "sparse":
        ranked = to_ranked(sparse)
    else:
        ranked = rrf_fuse(dense, sparse, args.alpha)

    reranked = False
    if args.rerank and ranked:
        n = min(len(ranked), args.rerank_n)
        ranked = do_rerank(args.query, ranked[:n], args.rerank_model,
                           get_key(args.key), min(args.topk, n))
        reranked = True

    hits, seen_parent = [], set()
    seeds, seed_label = [], {}
    for cid, info in ranked:
        if len(hits) >= args.topk:
            break
        meta = info["meta"]
        pid = meta["parent_id"]
        is_article = meta.get("node_type") == "Article"
        tag = "案例" if meta.get("node_type") == "Case" else meta.get("法规名", "")
        head = (f"{tag} {meta.get('条号', '')}".strip()
                if is_article else parents.get(pid, {}).get("标题", tag))
        first = pid not in seen_parent
        seen_parent.add(pid)
        hits.append({
            "score": info["score"], "法规名": meta.get("法规名", ""),
            "条号": meta.get("条号", ""), "node_type": meta.get("node_type"),
            "时效性": meta.get("时效性"), "parent_id": pid, "head": head,
            "is_article": is_article, "child": info.get("snip") or "",
            "parent_text": parents.get(pid, {}).get("text", "") if first else None,
        })
        if is_article and pid not in seed_label:      # 收集图扩展种子
            seeds.append(pid)
            seed_label[pid] = f"《{meta.get('法规名', '')}》{meta.get('条号', '')}".strip()

    expansion = []
    if args.expand and seeds:
        expansion, err = expand_seeds(args, seeds)
        if err:
            print(f"\n⚠ {err}")
    return {"query": args.query, "mode": args.mode, "reranked": reranked,
            "only_current": args.only_current, "alpha": args.alpha,
            "hits": hits, "seed_label": seed_label, "expansion": expansion}


def run(args):
    parents = load_parents()
    dense, sparse = [], []
    if args.mode in ("dense", "hybrid"):
        client = bv.get_client(args.key)
        dense = dense_rank(client, args.query, args.cand, args.only_current)
    if args.mode in ("sparse", "hybrid"):
        sparse = sparse_rank(load_bm25(), args.query, args.cand, args.only_current)

    if args.mode == "dense":
        ranked = to_ranked(dense)
    elif args.mode == "sparse":
        ranked = to_ranked(sparse)
    else:
        ranked = rrf_fuse(dense, sparse, args.alpha)

    reranked = False
    if args.rerank and ranked:
        n = min(len(ranked), args.rerank_n)
        ranked = do_rerank(args.query, ranked[:n], args.rerank_model,
                           get_key(args.key), min(args.topk, n))
        reranked = True

    tail = f" alpha={args.alpha}" if args.mode == "hybrid" else ""
    tail += " +rerank" if reranked else ""
    filt = " [仅现行有效]" if args.only_current else ""
    print(f"\n查询：{args.query} | 模式={args.mode}{tail}{filt}\n" + "=" * 70)
    shown, seen_parent = 0, set()
    seeds, seed_label = [], {}
    for cid, info in ranked:
        if shown >= args.topk:
            break
        meta = info["meta"]
        pid = meta["parent_id"]
        is_article = meta.get("node_type") == "Article"
        tag = "案例" if meta.get("node_type") == "Case" else meta.get("法规名", "")
        head = (f"{tag} {meta.get('条号', '')}".strip()
                if is_article else parents.get(pid, {}).get("标题", tag))
        flag = "" if meta.get("时效性") == "现行有效" else f"[{meta.get('时效性')}]"
        print(f"\n● score={info['score']:.4f} {flag} {head}")
        print(f"  child: {(info.get('snip') or '')[:90]}")
        if pid not in seen_parent:
            seen_parent.add(pid)
            print(f"  ↳parent[{pid}]: {parents.get(pid, {}).get('text', '')[:120]}")
        if is_article and pid not in seed_label:      # 收集图扩展种子
            seeds.append(pid)
            seed_label[pid] = f"《{meta.get('法规名', '')}》{meta.get('条号', '')}".strip()
        shown += 1

    if args.expand and seeds:
        emit_expansion(args, seeds, seed_label)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    ap.add_argument("--mode", choices=["hybrid", "dense", "sparse"], default="hybrid")
    ap.add_argument("--topk", type=int, default=6)
    ap.add_argument("--cand", type=int, default=50, help="每路候选数")
    ap.add_argument("--alpha", type=float, default=0.5, help="hybrid 稠密权重(稀疏=1-alpha)")
    ap.add_argument("--only-current", action="store_true", help="只检索现行有效")
    ap.add_argument("--rerank", action="store_true", help="召回后用 bge-reranker 精排")
    ap.add_argument("--rerank-n", type=int, default=30, help="送入 rerank 的候选数")
    ap.add_argument("--rerank-model", default=RERANK_MODEL)
    ap.add_argument("--expand", action="store_true", help="图多跳扩展关联条款(Neo4j)")
    ap.add_argument("--expand-per", type=int, default=5, help="每种子邻居数上限")
    ap.add_argument("--expand-max", type=int, default=20, help="关联条款总数上限")
    ap.add_argument("--neo4j-pwd", help="Neo4j 密码(默认取环境变量 NEO4J_PASSWORD)")
    ap.add_argument("--key")
    run(ap.parse_args())


if __name__ == "__main__":
    main()
