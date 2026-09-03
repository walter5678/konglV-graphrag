# -*- coding: utf-8 -*-
"""
compare_chunking.py —— 分块方法对照评测(第 6 章用)。

在**同一 BM25 检索器、同一 gold.jsonl、同一分词器与指标**下，仅替换 child 切分：
  A 父子分块      children.jsonl        (build_chunks.py)
  B 固定窗口分块  children_fixed.jsonl  (build_chunks_fixed.py)
从而把"分块策略"隔离为唯一变量，量化其对 Hit@k / Recall@k / MRR / nDCG@k 的影响。

为什么固定检索器为 BM25(sparse)：
  ① 隔离变量——嵌入模型/精排都不变，差异只能来自分块；
  ② 零成本可复现——不调任何 embedding/rerank API，评委可一键重跑；
  ③ 稀疏检索对"块是否与法条边界对齐"最敏感，最能暴露固定窗口的结构缺陷。

用法：python compare_chunking.py
产物：out/chunking_compare.json + out/chunking_compare_report.md
"""
import os, sys, json, math, pickle
from collections import defaultdict
sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))          # 5_向量库
KG = os.path.dirname(HERE)
OUT = os.path.join(HERE, "out")
EVAL = os.path.join(KG, "7_评测")
GOLD = os.path.join(EVAL, "gold.jsonl")

import build_bm25 as bb            # 复用同一 tokenize + 领域词典
from rank_bm25 import BM25Okapi

KS = (3, 5, 10)
TOPK = 10
CAND = 50

METHODS = {
    "A_父子分块(现方案)": "children.jsonl",
    "B_固定窗口分块":     "children_fixed.jsonl",
}


# ---------- 检索(纯 BM25，与 search.sparse_rank 同逻辑) ----------
def build_index(children_file):
    rows, seen = [], set()
    with open(os.path.join(OUT, children_file), encoding="utf-8") as f:
        for ln in f:
            r = json.loads(ln)
            if r["child_id"] in seen:
                continue
            seen.add(r["child_id"])
            rows.append(r)
    corpus = [bb.tokenize(r["embed_text"]) for r in rows]
    bm25 = BM25Okapi(corpus)
    metas = [{"parent_id": r["parent_id"], "时效性": r.get("时效性"),
              "node_type": r.get("node_type")} for r in rows]
    return bm25, metas, len(rows)


def sparse_ranked_parents(bm25, metas, query, only_current=True):
    """→ 去重保序的 parent_id 排名列表(与 eval_retrieval.ranked_parents 一致口径)。"""
    scores = bm25.get_scores(bb.tokenize(query))
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    seen, ranked, taken = set(), [], 0
    for i in order:
        if scores[i] <= 0 or taken >= CAND:
            break
        meta = metas[i]
        if only_current and meta.get("时效性") != "现行有效":
            continue
        taken += 1
        pid = meta["parent_id"]
        if pid and pid not in seen:
            seen.add(pid)
            ranked.append(pid)
        if len(ranked) >= TOPK:
            break
    return ranked


# ---------- 指标(照搬 eval_retrieval 的口径) ----------
def dcg(rels):
    return sum(r / math.log2(i + 2) for i, r in enumerate(rels))


def ndcg_at_k(ranked, gold, k):
    rels = [1 if pid in gold else 0 for pid in ranked[:k]]
    idcg = dcg([1] * min(len(gold), k))
    return (dcg(rels) / idcg) if idcg > 0 else 0.0


def per_question(ranked, gold, avoid, accept):
    gold, avoid, accept = set(gold), set(avoid), set(accept)
    relevant = gold | accept
    m = {}
    for k in KS:
        topk = set(ranked[:k])
        m[f"hit@{k}"] = 1.0 if (relevant & topk) else 0.0
        m[f"recall@{k}"] = len(gold & topk) / len(gold) if gold else 0.0
        m[f"ndcg@{k}"] = ndcg_at_k(ranked, gold, k)
    m["mrr"] = 0.0
    for i, pid in enumerate(ranked):
        if pid in relevant:
            m["mrr"] = 1.0 / (i + 1)
            break
    return m


def load_gold():
    rows = []
    with open(GOLD, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                rows.append(json.loads(ln))
    return rows


def eval_method(children_file, gold_rows):
    bm25, metas, n = build_index(children_file)
    details = []
    for q in gold_rows:
        ranked = sparse_ranked_parents(bm25, metas, q["question"])
        m = per_question(ranked, q["gold_parent_ids"],
                         q.get("avoid_ids", []), q.get("accept_ids", []))
        details.append({"id": q["id"], "category": q["category"],
                        "ranked_top5": ranked[:5], "gold": q["gold_parent_ids"], **m})
    keys = [f"hit@{k}" for k in KS] + [f"recall@{k}" for k in KS] + \
           [f"ndcg@{k}" for k in KS] + ["mrr"]
    agg = {kk: round(sum(d[kk] for d in details) / len(details), 4) for kk in keys}
    agg["child数"] = n
    return agg, details


def main():
    bb.load_domain_dict()                    # 与线上 BM25 完全一致的领域分词
    gold_rows = load_gold()
    print(f"评测集 {len(gold_rows)} 题 | 检索器=BM25(sparse) | only_current=开\n")

    results, all_details = {}, {}
    for name, f in METHODS.items():
        agg, details = eval_method(f, gold_rows)
        results[name] = agg
        all_details[name] = details
        print(f"── {name}: child={agg['child数']} "
              f"Hit@5={agg['hit@5']:.3f} Recall@5={agg['recall@5']:.3f} "
              f"MRR={agg['mrr']:.3f} nDCG@5={agg['ndcg@5']:.3f}")

    # 报告
    cols = ["hit@3", "hit@5", "hit@10", "recall@5", "recall@10", "mrr", "ndcg@5"]
    lines = ["# 分块方法对照评测报告\n",
             f"- 评测集：`gold.jsonl`（{len(gold_rows)} 题）",
             "- 检索器：**BM25 稀疏检索**（零成本、可复现；隔离分块为唯一变量）",
             "- 仅现行有效过滤：开｜每题取 top10\n",
             "## 指标对比\n",
             "| 方法 | child数 | " + " | ".join(cols) + " |",
             "|" + "---|" * (len(cols) + 2)]
    for name, agg in results.items():
        lines.append(f"| {name} | {agg['child数']} | " +
                     " | ".join(f"{agg[c]:.3f}" for c in cols) + " |")
    # 相对差
    a, b = list(results.values())
    lines.append("\n## A 相对 B 的提升\n")
    lines.append("| 指标 | A 父子 | B 固定 | 绝对差 | 相对提升 |")
    lines.append("|---|---:|---:|---:|---:|")
    for c in cols:
        d = a[c] - b[c]
        rel = (d / b[c] * 100) if b[c] else float("inf")
        lines.append(f"| {c} | {a[c]:.3f} | {b[c]:.3f} | +{d:.3f} | "
                     f"{'+%.1f%%' % rel if b[c] else '—'} |")
    p = os.path.join(OUT, "chunking_compare_report.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    json.dump({"aggregate": results, "details": all_details},
              open(os.path.join(OUT, "chunking_compare.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n✅ 报告 → {p}")
    print("\n" + "\n".join(lines[5:8 + len(results)]))


if __name__ == "__main__":
    main()
