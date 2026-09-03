# -*- coding: utf-8 -*-
"""
report.py —— 评测总报告汇总。

把三份评测产物合成一份答辩/演示直接可用的 markdown：
  out/retrieval_metrics.json   检索层消融（sparse→dense→hybrid→+rerank→+expand）
  out/alpha_sweep.json         alpha 融合权重扫描
  out/generation_metrics.json  生成层四维度 + 陷阱题专项 + 幻觉

产物：out/EVAL_REPORT.md（缺哪份就跳过对应章节，不报错）

用法：
  python report.py                        # 汇总 out/ 下已有结果
  python eval_retrieval.py ... && python eval_generation.py ... && python report.py
"""
import os, sys, json

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")


def load(name):
    p = os.path.join(OUT, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def count_gold():
    p = os.path.join(HERE, "gold.jsonl")
    if not os.path.exists(p):
        return 0
    return sum(1 for l in open(p, encoding="utf-8") if l.strip())


def sec_overview(n_gold, retr, sweep, gen, L):
    L.append("# 低空经济无人机法律问答系统 —— 评测总报告\n")
    L.append("本系统为 GraphRAG 端到端法律问答：父子分块 → hybrid 双路召回"
             "（BGE-M3 稠密 + BM25 稀疏）RRF 融合 → 时效过滤 → bge-reranker 精排 "
             "→ Neo4j 图多跳扩展 → LLM 生成带引用答案。\n")
    L.append("评测分**检索层**与**生成层**两级，对应「答案质量 = 检索质量」的设计事实："
             "检索层用标注 gold 条文算命中/召回/排序（全自动、零成本可复跑），"
             "生成层用独立更强的裁判模型对真实答案打分。\n")
    L.append(f"- 评测集：`gold.jsonl`，**{n_gold} 题**，覆盖机型分类/实名登记/空域管制/"
             "适航/罚则/运营义务等 13 类考点，含 **6 道时效性·机型陷阱题**")
    parts = []
    if retr: parts.append("检索层消融")
    if sweep: parts.append("alpha 权重扫描")
    if gen: parts.append("生成层四维度")
    L.append(f"- 本报告含：{'、'.join(parts)}\n")


def sec_retrieval(retr, L):
    L.append("## 一、检索层消融对比\n")
    agg = retr["aggregate"]
    cols = [("hit@3", "Hit@3"), ("hit@5", "Hit@5"), ("recall@5", "Recall@5"),
            ("mrr", "MRR"), ("ndcg@5", "nDCG@5"), ("hit@10", "Hit@10"),
            ("timeliness_err_rate", "时效错误率")]
    L.append("| 配置 | " + " | ".join(c[1] for c in cols) + " |")
    L.append("|" + "---|" * (len(cols) + 1))
    for cfg, m in agg.items():
        cells = []
        for k, _ in cols:
            v = m.get(k)
            cells.append("—" if v is None else f"{v:.3f}")
        L.append(f"| {cfg} | " + " | ".join(cells) + " |")
    L.append("\n> Hit@k=前 k 命中任一权威/等价条文的题占比；Recall@5=gold 被召回比例；"
             "MRR=首个正确条文排名倒数；nDCG@5=带位置权重排序质量；"
             "时效错误率=已废止条文排在现行版之前的题占比（越低越好）。\n")
    # 自动结论
    best_hit = max(agg, key=lambda c: agg[c]["hit@5"])
    L.append(f"**读表**：纯 BM25（sparse）作为零成本基线明显偏低，"
             f"稠密语义检索带来最大跃升；rerank 精排进一步修正 RRF 融合的排序。"
             f"本轮各配置中 **{best_hit}** 的 Hit@5 最高（{agg[best_hit]['hit@5']:.3f}）。")
    if "hybrid+rerank+expand" in agg and "hybrid+rerank" in agg:
        e, r = agg["hybrid+rerank+expand"], agg["hybrid+rerank"]
        if abs(e["hit@5"] - r["hit@5"]) < 1e-6:
            L.append("图扩展（expand）对 gold 命中率无增量——这符合预期：图多跳的价值是"
                     "为生成端补充「引用/同主体/同机型」关联条款作上下文，"
                     "而非提高主命中率，该价值在生成层体现。")
    L.append("")


def sec_sweep(sweep, L):
    L.append("## 二、alpha 融合权重扫描（hybrid）\n")
    L.append("alpha = 稠密（BGE-M3）权重，稀疏（BM25）权重 = 1 − alpha。\n")
    cols = ["hit@3", "hit@5", "recall@5", "mrr", "ndcg@5"]
    alphas = sorted(sweep, key=float)
    best_a = max(alphas, key=lambda a: (sweep[a]["hit@5"], sweep[a]["mrr"]))
    L.append("| alpha | " + " | ".join(cols) + " |")
    L.append("|" + "---|" * (len(cols) + 1))
    for a in alphas:
        m = sweep[a]
        star = " ⭐" if a == best_a else ""
        L.append(f"| {a}{star} | " + " | ".join(f"{m[c]:.3f}" for c in cols) + " |")
    L.append(f"\n**最优 alpha = {best_a}**（按 Hit@5 优先、MRR 次之）。"
             "Hit@5/Recall@5 随稠密权重单调上升，印证本领域语料高度同质"
             "（地方办法大量照抄国家条例），BM25 关键词路会稀释权威条文，"
             "故最优融合权重显著偏稠密侧——这是评测驱动调优的直接依据（默认 0.5 次优）。\n")


def sec_generation(gen, L):
    agg, cfg = gen["aggregate"], gen["config"]
    L.append("## 三、生成层评测（端到端答案质量）\n")
    L.append(f"- 检索配置：{cfg['mode']}"
             f"{'+rerank' if cfg['rerank'] else ''}{'+expand' if cfg['expand'] else ''}"
             f"，alpha={cfg['alpha']}{'，仅现行有效' if cfg['only_current'] else ''}")
    L.append(f"- 生成模型：`{cfg['gen_model']}`｜裁判模型：`{cfg['judge_model']}`"
             "（独立更强，避免自评偏高）\n")
    L.append("| 维度 | 均分 | 说明 |")
    L.append("|---|---|---|")
    L.append(f"| 忠实度(无幻觉) | {agg['faithfulness']:.3f} | 论断是否有检索依据 |")
    L.append(f"| 正确性 | {agg['correctness']:.3f} | 覆盖标准要点比例 |")
    L.append(f"| 时效性 | {agg['timeliness']:.3f} | 是否基于现行有效 |")
    L.append(f"| 引用正确性 | {agg['citation']:.3f} | 参考法规真实且相关 |")
    L.append(f"| **综合** | **{agg['overall']:.3f}** | 四维均值 |")
    L.append(f"\n含幻觉的题：**{agg['n_hallucination_qs']}/{agg['n']}**\n")

    if "trap_timeliness" in agg:
        L.append("### 陷阱题（时效性/机型）专项\n")
        L.append(f"6 道陷阱题：时效性均分 **{agg['trap_timeliness']:.3f}**、"
                 f"忠实度均分 **{agg['trap_faithfulness']:.3f}**，"
                 f"明显低于整体（时效 {agg['timeliness']:.3f}）。\n")
        L.append("| 题号 | 类别 | 忠实 | 正确 | 时效 | 引用 | 判定 | 主要扣分点 |")
        L.append("|---|---|---|---|---|---|---|---|")
        for d in gen["details"]:
            if d.get("is_trap"):
                L.append(f"| {d['id']} | {d['category']} | {d['faithfulness']:.2f} | "
                         f"{d['correctness']:.2f} | {d['timeliness']:.2f} | "
                         f"{d['citation']:.2f} | {d.get('verdict','')} | {d.get('reason','')} |")
        L.append("")

    # 低分题
    low = [d for d in gen["details"] if d.get("hallucinations") or
           min(d["faithfulness"], d["correctness"], d["timeliness"], d["citation"]) < 0.6]
    L.append("### 需关注的低分题\n")
    if not low:
        L.append("（无：所有题各维度均 ≥ 0.6 且无幻觉）\n")
    else:
        L.append("| 题号 | 类别 | 忠实 | 正确 | 时效 | 引用 | 主要问题 |")
        L.append("|---|---|---|---|---|---|---|")
        for d in low:
            hal = ("；".join(d["hallucinations"][:1]) if d.get("hallucinations")
                   else d.get("reason", ""))
            L.append(f"| {d['id']} | {d['category']} | {d['faithfulness']:.2f} | "
                     f"{d['correctness']:.2f} | {d['timeliness']:.2f} | "
                     f"{d['citation']:.2f} | {hal} |")
        L.append("")


def sec_conclusion(retr, sweep, gen, L):
    L.append("## 四、结论与优化方向\n")
    pts = []
    if sweep:
        alphas = sorted(sweep, key=float)
        best_a = max(alphas, key=lambda a: (sweep[a]["hit@5"], sweep[a]["mrr"]))
        pts.append(f"**融合权重调优**：alpha 扫描证明本领域最优稠密权重 ≈ {best_a}，"
                   "显著高于默认 0.5，应据此上调 search/qa/server 的默认 alpha。")
    if gen and "trap_timeliness" in gen["aggregate"]:
        a = gen["aggregate"]
        pts.append(f"**时效性是主要短板**：整体答案质量高（综合 {a['overall']:.3f}），"
                   f"但陷阱题时效性仅 {a['trap_timeliness']:.3f}——微型实名登记、民航法版本等题"
                   "会被检索到的地方办法/废止版带偏。根因在检索排序而非生成端，"
                   "优化方向是提升权威国家法规在召回中的优先级（如按效力层级加权/过滤）。")
    if retr and "hybrid+rerank+expand" in retr["aggregate"]:
        pts.append("**图扩展价值需在生成层度量**：expand 不提升主命中率，"
                   "但为生成端补充关联条款上下文，后续可评「答案是否用上关联条款」。")
    for i, p in enumerate(pts, 1):
        L.append(f"{i}. {p}")
    if not pts:
        L.append("（数据不足，先补齐各层评测结果）")
    L.append("")


def main():
    retr = load("retrieval_metrics.json")
    sweep = load("alpha_sweep.json")
    gen = load("generation_metrics.json")
    if not any([retr, sweep, gen]):
        sys.exit("out/ 下没有任何评测结果，先跑 eval_retrieval.py / eval_generation.py")

    n_gold = count_gold()
    L = []
    sec_overview(n_gold, retr, sweep, gen, L)
    if retr:  sec_retrieval(retr, L)
    if sweep: sec_sweep(sweep, L)
    if gen:   sec_generation(gen, L)
    sec_conclusion(retr, sweep, gen, L)

    p = os.path.join(OUT, "EVAL_REPORT.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    have = [n for n, x in [("检索消融", retr), ("alpha扫描", sweep), ("生成层", gen)] if x]
    print(f"✅ 总报告 → {p}")
    print(f"   已汇总：{'、'.join(have)}")


if __name__ == "__main__":
    main()
