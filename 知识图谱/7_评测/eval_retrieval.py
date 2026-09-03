# -*- coding: utf-8 -*-
"""
eval_retrieval.py —— 检索层评测 + 消融对比。

对 gold.jsonl 每题，在多种检索配置下跑 search.retrieve()，用 hits[].parent_id
对照 gold_parent_ids 计算 Hit@k / Recall@k / MRR / nDCG@k，用 avoid_ids 计算
时效错误率，并单独度量图扩展(expand)带来的召回增量。

配置矩阵(按需选跑)：
  sparse                     纯 BM25，**无需任何 API key**（零成本，可反复跑）
  dense                      纯 BGE-M3 向量           （需 SILICONFLOW_API_KEY）
  hybrid                     dense+sparse RRF 融合     （需 key）
  hybrid+rerank              融合后 bge-reranker 精排  （需 key）
  hybrid+rerank+expand       再加 Neo4j 图多跳         （需 key + Neo4j）

用法：
  # 零成本：只跑 sparse（不调任何嵌入/精排 API）
  python eval_retrieval.py --configs sparse

  # 全消融（需 SiliconFlow key，expand 还需 Neo4j 起着）
  set SILICONFLOW_API_KEY=sk-xxx
  python eval_retrieval.py --configs sparse,dense,hybrid,hybrid+rerank,hybrid+rerank+expand --neo4j-pwd 12345678

产物：
  out/retrieval_metrics.json   每配置聚合指标 + 每题明细
  out/retrieval_report.md      消融对比表 + 陷阱题/图扩展明细（答辩直接用）
"""
import os, sys, json, math, argparse, time
from types import SimpleNamespace

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
GOLD = os.path.join(HERE, "gold.jsonl")

# 复用 5_向量库/search.py 的检索链
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "5_向量库"))
import search as se

KS = (3, 5, 10)          # 评测的 k 值
TOPK = 10                # 每次检索取的主命中数（≥ max(KS)）
RERANK_MODEL = se.RERANK_MODEL

# 配置名 → retrieve() 参数补丁
CONFIGS = {
    "sparse":               dict(mode="sparse", rerank=False, expand=False),
    "dense":                dict(mode="dense",  rerank=False, expand=False),
    "hybrid":               dict(mode="hybrid", rerank=False, expand=False),
    "hybrid+rerank":        dict(mode="hybrid", rerank=True,  expand=False),
    "hybrid+rerank+expand": dict(mode="hybrid", rerank=True,  expand=True),
}


def load_gold():
    rows = []
    with open(GOLD, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_args(query, cfg, only_current, key, neo4j_pwd, alpha=0.5):
    """按配置拼 retrieve() 所需的 args 命名空间。"""
    base = dict(query=query, topk=TOPK, cand=50, alpha=alpha,
                only_current=only_current, rerank=False, rerank_n=30,
                rerank_model=RERANK_MODEL, expand=False, expand_per=5,
                expand_max=20, neo4j_pwd=neo4j_pwd, key=key)
    base.update(CONFIGS[cfg])
    return SimpleNamespace(**base)


def ranked_parents(hits):
    """hits → 去重后保序的 parent_id 排名列表(检索层评测的基本单位)。"""
    seen, order = set(), []
    for h in hits:
        pid = h.get("parent_id")
        if pid and pid not in seen:
            seen.add(pid)
            order.append(pid)
    return order


def dcg(rels):
    return sum(r / math.log2(i + 2) for i, r in enumerate(rels))


def ndcg_at_k(ranked, gold, k):
    rels = [1 if pid in gold else 0 for pid in ranked[:k]]
    ideal = [1] * min(len(gold), k)
    idcg = dcg(ideal)
    return (dcg(rels) / idcg) if idcg > 0 else 0.0


def per_question_metrics(ranked, gold, avoid, accept=()):
    """单题：Hit@k / Recall@k / MRR / nDCG@k / 时效错误。

    gold  = 最权威、必须召回的核心条文（Recall 分母、nDCG 相关性以它为准）。
    accept= 等价可接受条文（同法邻条 / 另一部同样对口的法规）。命中 gold 或
            accept 都算 Hit / 计入 MRR，但**不进 Recall 分母**——避免用宽口径
            灌高召回率，只用来「不冤枉答对邻条的情况」。
    """
    gold, avoid, accept = set(gold), set(avoid), set(accept)
    relevant = gold | accept          # Hit/MRR 口径
    m = {}
    for k in KS:
        topk = set(ranked[:k])
        m[f"hit@{k}"]    = 1.0 if (relevant & topk) else 0.0
        m[f"recall@{k}"] = len(gold & topk) / len(gold) if gold else 0.0
        m[f"ndcg@{k}"]   = ndcg_at_k(ranked, gold, k)
    # MRR：第一个相关(gold 或 accept)条文的排名倒数(全列表)
    m["mrr"] = 0.0
    for i, pid in enumerate(ranked):
        if pid in relevant:
            m["mrr"] = 1.0 / (i + 1)
            break
    # 时效错误：avoid(已废止/易混)在 top-k 内且排在首个 gold 之前(或 gold 缺席)
    m["timeliness_err"] = None
    if avoid:
        topk = ranked[:max(KS)]
        avoid_ranks = [i for i, pid in enumerate(topk) if pid in avoid]
        gold_ranks  = [i for i, pid in enumerate(topk) if pid in gold]
        if avoid_ranks:
            first_avoid = min(avoid_ranks)
            first_gold = min(gold_ranks) if gold_ranks else 10**9
            m["timeliness_err"] = 1.0 if first_avoid < first_gold else 0.0
        else:
            m["timeliness_err"] = 0.0
    return m


def expand_gain(res, gold, ranked):
    """图扩展的召回增量：gold 中「主命中没排到、却被图扩展补回」的条数。"""
    exp_ids = {d.get("id") for d in res.get("expansion", [])}
    in_hits = set(ranked)
    gained = [g for g in gold if g not in in_hits and g in exp_ids]
    return gained


def run_config(cfg, gold_rows, only_current, key, neo4j_pwd, alpha=0.5):
    """跑一个配置的全部题目 → (聚合指标, 每题明细)。"""
    details, agg = [], {}
    t0 = time.time()
    for q in gold_rows:
        args = build_args(q["question"], cfg, only_current, key, neo4j_pwd, alpha)
        res = se.retrieve(args)
        ranked = ranked_parents(res["hits"])
        m = per_question_metrics(ranked, q["gold_parent_ids"], q.get("avoid_ids", []),
                                 q.get("accept_ids", []))
        rec = {"id": q["id"], "category": q["category"], "difficulty": q["difficulty"],
               "ranked_top5": ranked[:5], "gold": q["gold_parent_ids"], **m}
        if CONFIGS[cfg]["expand"]:
            gained = expand_gain(res, set(q["gold_parent_ids"]), ranked)
            rec["expand_gain"] = gained
            rec["n_expansion"] = len(res.get("expansion", []))
        details.append(rec)
    # 聚合(时效错误率只在有 avoid 的题上算)
    keys = [f"hit@{k}" for k in KS] + [f"recall@{k}" for k in KS] + \
           [f"ndcg@{k}" for k in KS] + ["mrr"]
    for kk in keys:
        agg[kk] = round(sum(d[kk] for d in details) / len(details), 4)
    trap = [d for d in details if d["timeliness_err"] is not None]
    agg["timeliness_err_rate"] = (round(sum(d["timeliness_err"] for d in trap) / len(trap), 4)
                                  if trap else None)
    agg["n_trap"] = len(trap)
    if CONFIGS[cfg]["expand"]:
        agg["expand_gain_total"] = sum(len(d.get("expand_gain", [])) for d in details)
        agg["expand_gain_questions"] = sum(1 for d in details if d.get("expand_gain"))
    agg["elapsed_s"] = round(time.time() - t0, 1)
    return agg, details


def fmt_table(all_agg):
    """消融对比表(markdown)。"""
    cols = ["hit@3", "hit@5", "recall@5", "mrr", "ndcg@5", "hit@10", "timeliness_err_rate"]
    head = "| 配置 | " + " | ".join(cols) + " |"
    sep = "|" + "---|" * (len(cols) + 1)
    lines = [head, sep]
    for cfg, agg in all_agg.items():
        cells = []
        for c in cols:
            v = agg.get(c)
            cells.append("—" if v is None else f"{v:.3f}")
        lines.append(f"| {cfg} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def write_report(all_agg, all_details, only_current):
    lines = ["# 检索层评测报告（消融对比）\n"]
    lines.append(f"- 评测集：`gold.jsonl`（{len(next(iter(all_details.values())))} 题）")
    lines.append(f"- only_current（仅现行有效过滤）：{'开' if only_current else '关'}")
    lines.append(f"- 每题取主命中 top{TOPK}，指标 k ∈ {list(KS)}\n")
    lines.append("## 一、总体消融对比\n")
    lines.append(fmt_table(all_agg))
    lines.append("\n> Hit@k=前 k 命中任一 gold 的题占比；Recall@5=gold 被召回比例；")
    lines.append("> MRR=首个正确条文排名倒数；nDCG@5=带位置权重的排序质量；")
    lines.append("> 时效错误率=已废止/易混条文排在现行版之前的题占比（越低越好）。\n")

    # 图扩展增量
    for cfg, agg in all_agg.items():
        if "expand_gain_total" in agg:
            lines.append("## 二、图扩展召回增量\n")
            lines.append(f"配置 `{cfg}`：图多跳共补回 **{agg['expand_gain_total']}** 条主命中漏掉的 gold 条文，"
                         f"覆盖 **{agg['expand_gain_questions']}** 道题。明细：\n")
            for d in all_details[cfg]:
                if d.get("expand_gain"):
                    lines.append(f"- {d['id']}（{d['category']}）：补回 {d['expand_gain']}")
            lines.append("")

    # 陷阱题明细
    lines.append("## 三、陷阱题明细（时效性/机型）\n")
    ref_cfg = list(all_agg.keys())[-1]   # 用最强配置看
    lines.append(f"（配置：`{ref_cfg}`）\n")
    lines.append("| 题号 | 类别 | Hit@5 | 时效错误 | top5 命中 |")
    lines.append("|---|---|---|---|---|")
    for d in all_details[ref_cfg]:
        if d["timeliness_err"] is not None:
            hit = "✓" if d["hit@5"] else "✗"
            terr = "⚠是" if d["timeliness_err"] else "否"
            got = "、".join(p for p in d["ranked_top5"] if p in set(d["gold"])) or "—"
            lines.append(f"| {d['id']} | {d['category']} | {hit} | {terr} | {got} |")

    p = os.path.join(OUT, "retrieval_report.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return p


def run_alpha_sweep(gold_rows, alphas, with_rerank, only_current, key, neo4j_pwd):
    """在多个 alpha 下跑 hybrid（可选叠 rerank），找最优稠密/稀疏融合权重。

    alpha=稠密权重（稀疏=1-alpha）。alpha=1.0 等价纯 dense，0.0 等价纯 sparse。
    本领域地方办法大量照抄国家条例、关键词同质，稀疏路易稀释权威条文，
    故预期最优 alpha 明显偏稠密侧（>0.5）。
    """
    cfg = "hybrid+rerank" if with_rerank else "hybrid"
    sweep = {}
    for a in alphas:
        print(f"── alpha={a:.2f}（{cfg}）……", flush=True)
        agg, details = run_config(cfg, gold_rows, only_current, key, neo4j_pwd, alpha=a)
        sweep[a] = {"agg": agg, "details": details}
        print(f"   Hit@5={agg['hit@5']:.3f} Recall@5={agg['recall@5']:.3f} "
              f"MRR={agg['mrr']:.3f} nDCG@5={agg['ndcg@5']:.3f}  ({agg['elapsed_s']}s)")
    return cfg, sweep


def write_sweep_report(cfg, sweep, only_current):
    n = len(next(iter(sweep.values()))["details"])
    best_a = max(sweep, key=lambda a: (sweep[a]["agg"]["hit@5"], sweep[a]["agg"]["mrr"]))
    lines = [f"# alpha 融合权重扫描（{cfg}）\n"]
    lines.append(f"- 评测集：`gold.jsonl`（{n} 题）｜only_current：{'开' if only_current else '关'}")
    lines.append(f"- alpha=稠密(BGE-M3)权重，稀疏(BM25)权重=1-alpha\n")
    cols = ["hit@3", "hit@5", "recall@5", "mrr", "ndcg@5", "hit@10"]
    lines.append("| alpha | " + " | ".join(cols) + " |")
    lines.append("|" + "---|" * (len(cols) + 1))
    for a in sorted(sweep):
        agg = sweep[a]["agg"]
        star = " ⭐" if a == best_a else ""
        lines.append(f"| {a:.2f}{star} | " + " | ".join(f"{agg[c]:.3f}" for c in cols) + " |")
    lines.append(f"\n**最优 alpha = {best_a:.2f}**（按 Hit@5 优先、MRR 次之）。")
    lines.append(f"稠密权重越高越好，印证了「稀疏路的同质地方办法会稀释权威国家条文」的判断。\n")
    p = os.path.join(OUT, "alpha_sweep_report.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return p, best_a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", default="sparse",
                    help="逗号分隔，可选：" + ",".join(CONFIGS))
    ap.add_argument("--only-current", action="store_true",
                    help="检索时只保留现行有效（推荐开，体现时效过滤）")
    ap.add_argument("--key", help="SiliconFlow key（dense/hybrid/rerank 需要）")
    ap.add_argument("--neo4j-pwd", help="Neo4j 密码（expand 需要）")
    ap.add_argument("--alpha-sweep",
                    help="alpha 扫描模式：逗号分隔的稠密权重，如 0.3,0.5,0.7,0.9")
    ap.add_argument("--sweep-rerank", action="store_true",
                    help="alpha 扫描时叠加 rerank（更贴近线上，但更慢/更费 key）")
    args = ap.parse_args()

    gold_rows = load_gold()

    # ── alpha 扫描模式 ──
    if args.alpha_sweep:
        alphas = [float(x) for x in args.alpha_sweep.split(",") if x.strip()]
        print(f"评测集 {len(gold_rows)} 题 | alpha 扫描 {alphas} | "
              f"rerank={'开' if args.sweep_rerank else '关'} | only_current={args.only_current}\n")
        cfg, sweep = run_alpha_sweep(gold_rows, alphas, args.sweep_rerank,
                                     args.only_current, args.key, args.neo4j_pwd)
        with open(os.path.join(OUT, "alpha_sweep.json"), "w", encoding="utf-8") as f:
            json.dump({a: sweep[a]["agg"] for a in sweep}, f, ensure_ascii=False, indent=2)
        rp, best_a = write_sweep_report(cfg, sweep, args.only_current)
        print("\n" + "=" * 60)
        cols = ["hit@3", "hit@5", "recall@5", "mrr", "ndcg@5"]
        print("| alpha | " + " | ".join(cols) + " |")
        print("|" + "---|" * (len(cols) + 1))
        for a in sorted(sweep):
            agg = sweep[a]["agg"]
            star = " ⭐" if a == best_a else ""
            print(f"| {a:.2f}{star} | " + " | ".join(f"{agg[c]:.3f}" for c in cols) + " |")
        print("=" * 60)
        print(f"\n✅ 最优 alpha={best_a:.2f} | 明细 → out/alpha_sweep.json | 报告 → {rp}")
        return

    cfgs = [c.strip() for c in args.configs.split(",") if c.strip()]
    bad = [c for c in cfgs if c not in CONFIGS]
    if bad:
        sys.exit(f"✗ 未知配置：{bad}，可选：{list(CONFIGS)}")

    gold_rows = load_gold()
    print(f"评测集 {len(gold_rows)} 题 | 配置 {cfgs} | only_current={args.only_current}\n")

    all_agg, all_details = {}, {}
    for cfg in cfgs:
        print(f"── 跑配置：{cfg} ……", flush=True)
        try:
            agg, details = run_config(cfg, gold_rows, args.only_current,
                                      args.key, args.neo4j_pwd)
        except SystemExit as e:            # get_key/get_client 缺 key 时的 sys.exit
            print(f"   跳过 {cfg}：{e}")
            continue
        all_agg[cfg] = agg
        all_details[cfg] = details
        line = f"   Hit@5={agg['hit@5']:.3f} Recall@5={agg['recall@5']:.3f} " \
               f"MRR={agg['mrr']:.3f} nDCG@5={agg['ndcg@5']:.3f}"
        if agg["timeliness_err_rate"] is not None:
            line += f" 时效错误率={agg['timeliness_err_rate']:.3f}"
        line += f"  ({agg['elapsed_s']}s)"
        print(line)

    if not all_agg:
        sys.exit("没有成功跑完的配置（多半是缺 API key，可先 --configs sparse）")

    with open(os.path.join(OUT, "retrieval_metrics.json"), "w", encoding="utf-8") as f:
        json.dump({"aggregate": all_agg, "details": all_details},
                  f, ensure_ascii=False, indent=2)
    rp = write_report(all_agg, all_details, args.only_current)

    print("\n" + "=" * 60)
    print(fmt_table(all_agg))
    print("=" * 60)
    print(f"\n✅ 指标 → out/retrieval_metrics.json")
    print(f"✅ 报告 → {rp}")


if __name__ == "__main__":
    main()
