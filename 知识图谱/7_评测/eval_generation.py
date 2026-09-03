# -*- coding: utf-8 -*-
"""
eval_generation.py —— 生成层评测（端到端答案质量）。

对 gold.jsonl 每题：跑真实检索链(search.retrieve) → 拼上下文(qa.build_context)
→ 生成答案(qa.stream_answer) → 用 **独立的更强裁判模型** 打四个维度分：

  1. faithfulness  忠实度/无幻觉：答案每个论断能否在检索上下文里找到依据（法律问答最致命的是编造）
  2. correctness   正确性：答案覆盖了多少 gold 的 key_points（0~1）
  3. timeliness    时效性：是否基于现行有效、有无把已废止条文当现行依据（陷阱题重点）
  4. citation      引用正确性：末行「参考法规」是否都真实相关、有无编造法规名

生成端与裁判端都走 OpenAI 兼容接口，**分开配置**避免自评偏高：
  生成：LLM_API_KEY / LLM_BASE_URL / LLM_MODEL          (沿用 qa.py 约定)
  裁判：JUDGE_KEY   / JUDGE_BASE_URL / JUDGE_MODEL        (默认同 key，模型换更强的)

用法：
  set SILICONFLOW_API_KEY=sk-xxx            # 检索端(BGE-M3/rerank)
  set LLM_API_KEY=sk-xxx                    # 生成端
  set JUDGE_KEY=sk-xxx                      # 裁判端(默认同上)
  python eval_generation.py --mode hybrid --rerank --only-current --key sk-xxx \
      --gen-model deepseek-ai/DeepSeek-V3 --judge-model Qwen/Qwen2.5-72B-Instruct \
      --gen-base https://api.siliconflow.cn/v1 --judge-base https://api.siliconflow.cn/v1
  # 只跑前 N 题冒烟：--limit 5
  # 复用已生成答案、只重评：--reuse

产物：
  out/generation_answers.jsonl   每题：检索上下文 + 生成的答案（可复用重评）
  out/generation_metrics.json    每题四维度分 + 聚合
  out/generation_report.md       四维度均分 + 陷阱题逐题 + 低分题清单
"""
import os, sys, json, argparse, time
from types import SimpleNamespace

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
GOLD = os.path.join(HERE, "gold.jsonl")
ANSWERS = os.path.join(OUT, "generation_answers.jsonl")

# 复用检索链与问答上下文构建
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "5_向量库"))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "6_问答"))
import search as se
import qa

RERANK_MODEL = se.RERANK_MODEL

JUDGE_SYS = """你是严格的法律问答质检专家。给你【用户问题】【检索到的法律条文(事实依据)】\
【标准要点】【待评答案】，请**只依据给定材料**对答案打分，输出 JSON。

评分维度(均为 0.0~1.0)：
- faithfulness 忠实度：答案的每个论断是否都能在【检索到的法律条文】里找到依据。
  只要有一处编造/无依据的法律结论就应显著扣分；完全有据=1.0。
- correctness 正确性：答案覆盖了多少【标准要点】的核心信息(按要点命中比例)。
- timeliness 时效性：是否基于现行有效规定作答；若把标注[已废止]的内容当现行依据陈述，判低分；
  正确规避或未涉及失效问题=1.0；无时效风险的题默认 1.0。
- citation 引用正确性：答案末行「参考法规：《…》」列出的法规是否都真实出现在检索材料中且相关；
  有编造或明显不相关的法规名则扣分；无参考法规行判 0.5。

同时给出：
- hallucinations: 数组，列出答案中无依据/编造的具体论断(没有则空数组)
- verdict: "good"|"fair"|"poor" 总体判断
- reason: 一句话中文说明主要扣分点

严格输出如下 JSON（不要多余文字）：
{"faithfulness":0.0,"correctness":0.0,"timeliness":0.0,"citation":0.0,
 "hallucinations":[],"verdict":"good","reason":""}"""


def load_gold(limit=None):
    rows = []
    with open(GOLD, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows[:limit] if limit else rows


def build_retrieve_args(query, args):
    return SimpleNamespace(
        query=query, mode=args.mode, topk=args.topk, cand=50, alpha=args.alpha,
        only_current=args.only_current, rerank=args.rerank, rerank_n=30,
        rerank_model=RERANK_MODEL, expand=args.expand, expand_per=5,
        expand_max=10, neo4j_pwd=args.neo4j_pwd, key=args.key)


def gen_client(args):
    from openai import OpenAI
    key = args.gen_key or os.environ.get("LLM_API_KEY") or os.environ.get("SILICONFLOW_API_KEY")
    if not key:
        sys.exit("✗ 生成端缺 key：设 LLM_API_KEY 或传 --gen-key")
    return OpenAI(api_key=key, base_url=args.gen_base), key


def judge_client(args):
    from openai import OpenAI
    key = args.judge_key or os.environ.get("JUDGE_KEY") or args.gen_key \
        or os.environ.get("LLM_API_KEY") or os.environ.get("SILICONFLOW_API_KEY")
    if not key:
        sys.exit("✗ 裁判端缺 key：设 JUDGE_KEY 或传 --judge-key")
    return OpenAI(api_key=key, base_url=args.judge_base)


def generate_answer(client, model, context, query):
    """非流式一次拿全文(评测不需要流式)。"""
    r = client.chat.completions.create(
        model=model, temperature=0.2,
        messages=qa.build_messages(context, query))
    return r.choices[0].message.content or ""


def judge_answer(client, model, q, context, answer, retry=5):
    """裁判打分 → dict。强制 JSON，解析失败则记 error。429 限速自动退避重试。"""
    key_points = "\n".join(f"- {p}" for p in q.get("key_points", []))
    trap = q.get("trap", "")
    user = (f"【用户问题】{q['question']}\n\n"
            f"【检索到的法律条文】\n{context}\n\n"
            f"【标准要点】\n{key_points}\n"
            + (f"\n【本题时效性风险提示】{trap}\n" if trap else "")
            + f"\n【待评答案】\n{answer}\n\n请按系统要求输出评分 JSON。")
    raw = "{}"
    for i in range(retry):
        try:
            r = client.chat.completions.create(
                model=model, temperature=0.0,
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": JUDGE_SYS},
                          {"role": "user", "content": user}])
            raw = r.choices[0].message.content or "{}"
            break
        except Exception as e:
            if "429" in str(e) or "rate limit" in str(e).lower() or "TPM" in str(e):
                wait = min(30, 5 * (i + 1))       # 5,10,15,20,25s 线性退避
                print(f"      ⏳ 限速，{wait}s 后重试({i+1}/{retry})", flush=True)
                time.sleep(wait)
                continue
            return {"error": f"裁判调用失败: {str(e)[:120]}", "faithfulness": 0.0,
                    "correctness": 0.0, "timeliness": 0.0, "citation": 0.0,
                    "hallucinations": [], "verdict": "poor", "reason": "调用失败"}
    try:
        d = json.loads(raw)
        for k in ("faithfulness", "correctness", "timeliness", "citation"):
            d[k] = float(d.get(k, 0.0))
        d.setdefault("hallucinations", [])
        d.setdefault("verdict", "")
        d.setdefault("reason", "")
        return d
    except Exception as e:
        return {"error": f"裁判JSON解析失败: {e}", "raw": raw[:300],
                "faithfulness": 0.0, "correctness": 0.0,
                "timeliness": 0.0, "citation": 0.0,
                "hallucinations": [], "verdict": "poor", "reason": "解析失败"}


def stage_generate(gold_rows, args):
    """检索 + 生成，落盘 answers.jsonl（供复用重评）。"""
    gc, _ = gen_client(args)
    recs = []
    with open(ANSWERS, "w", encoding="utf-8") as f:
        for i, q in enumerate(gold_rows, 1):
            rargs = build_retrieve_args(q["question"], args)
            res = se.retrieve(rargs)
            context = qa.build_context(res)
            ans = generate_answer(gc, args.gen_model, context, q["question"])
            n_exp = len(res.get("expansion", []))
            rec = {"id": q["id"], "question": q["question"], "context": context,
                   "answer": ans, "n_hits": len(res["hits"]), "n_expansion": n_exp}
            recs.append(rec)
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"  [{i}/{len(gold_rows)}] {q['id']} 生成完毕({len(ans)}字)", flush=True)
    return recs


def load_answers():
    recs = {}
    with open(ANSWERS, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                recs[r["id"]] = r
    return recs


def main():
    ap = argparse.ArgumentParser()
    # 检索参数(透传)
    ap.add_argument("--mode", choices=["hybrid", "dense", "sparse"], default="hybrid")
    ap.add_argument("--topk", type=int, default=6)
    ap.add_argument("--alpha", type=float, default=0.5)
    ap.add_argument("--only-current", action="store_true")
    ap.add_argument("--rerank", action="store_true")
    ap.add_argument("--expand", action="store_true")
    ap.add_argument("--neo4j-pwd")
    ap.add_argument("--key", help="检索端 SiliconFlow key(BGE-M3/rerank)")
    # 生成端
    ap.add_argument("--gen-model", default=os.environ.get("LLM_MODEL", "deepseek-ai/DeepSeek-V3"))
    ap.add_argument("--gen-base", default=os.environ.get("LLM_BASE_URL", "https://api.siliconflow.cn/v1"))
    ap.add_argument("--gen-key")
    # 裁判端(独立、更强，避免自评)
    ap.add_argument("--judge-model", default=os.environ.get("JUDGE_MODEL", "Qwen/Qwen2.5-72B-Instruct"))
    ap.add_argument("--judge-base", default=os.environ.get("JUDGE_BASE", "https://api.siliconflow.cn/v1"))
    ap.add_argument("--judge-key")
    # 流程控制
    ap.add_argument("--limit", type=int, help="只跑前 N 题(冒烟)")
    ap.add_argument("--reuse", action="store_true", help="复用已生成的 answers.jsonl，只重跑裁判")
    ap.add_argument("--judge-sleep", type=float, default=2.0,
                    help="裁判每题间隔秒数(缓解 TPM 限速)")
    args = ap.parse_args()

    gold_rows = load_gold(args.limit)
    gold_by_id = {q["id"]: q for q in gold_rows}
    print(f"生成层评测 {len(gold_rows)} 题 | 检索={args.mode}"
          f"{'+rerank' if args.rerank else ''}{'+expand' if args.expand else ''}"
          f"{' 仅现行' if args.only_current else ''}")
    print(f"生成模型={args.gen_model} | 裁判模型={args.judge_model}\n")

    # ① 生成(或复用)
    if args.reuse and os.path.exists(ANSWERS):
        print("复用已有答案 answers.jsonl，跳过生成")
        answers = load_answers()
        answers = {k: v for k, v in answers.items() if k in gold_by_id}
    else:
        print("── 阶段1：检索 + 生成答案 ……")
        recs = stage_generate(gold_rows, args)
        answers = {r["id"]: r for r in recs}

    # ② 裁判打分
    print("\n── 阶段2：独立裁判打分 ……")
    jc = judge_client(args)
    details, t0 = [], time.time()
    for i, q in enumerate(gold_rows, 1):
        rec = answers.get(q["id"])
        if not rec:
            continue
        v = judge_answer(jc, args.judge_model, q, rec["context"], rec["answer"])
        det = {"id": q["id"], "category": q["category"], "difficulty": q["difficulty"],
               "is_trap": bool(q.get("trap")), **{k: v[k] for k in
               ("faithfulness", "correctness", "timeliness", "citation")},
               "verdict": v.get("verdict", ""), "reason": v.get("reason", ""),
               "hallucinations": v.get("hallucinations", [])}
        if "error" in v:
            det["error"] = v["error"]
        details.append(det)
        print(f"  [{i}/{len(gold_rows)}] {q['id']} "
              f"忠实{det['faithfulness']:.2f} 正确{det['correctness']:.2f} "
              f"时效{det['timeliness']:.2f} 引用{det['citation']:.2f} [{det['verdict']}]",
              flush=True)
        time.sleep(args.judge_sleep)      # 主动节流，缓解裁判端 TPM 限速

    # ③ 聚合
    dims = ("faithfulness", "correctness", "timeliness", "citation")
    agg = {d: round(sum(x[d] for x in details) / len(details), 4) for d in dims}
    agg["overall"] = round(sum(agg[d] for d in dims) / len(dims), 4)
    traps = [x for x in details if x["is_trap"]]
    if traps:
        agg["trap_timeliness"] = round(sum(x["timeliness"] for x in traps) / len(traps), 4)
        agg["trap_faithfulness"] = round(sum(x["faithfulness"] for x in traps) / len(traps), 4)
    agg["n"] = len(details)
    agg["n_hallucination_qs"] = sum(1 for x in details if x["hallucinations"])
    agg["elapsed_s"] = round(time.time() - t0, 1)

    with open(os.path.join(OUT, "generation_metrics.json"), "w", encoding="utf-8") as f:
        json.dump({"config": {"mode": args.mode, "rerank": args.rerank,
                   "expand": args.expand, "alpha": args.alpha,
                   "only_current": args.only_current, "gen_model": args.gen_model,
                   "judge_model": args.judge_model},
                   "aggregate": agg, "details": details}, f,
                  ensure_ascii=False, indent=2)
    rp = write_report(agg, details, args)
    print("\n" + "=" * 60)
    print(f"忠实度 {agg['faithfulness']:.3f} | 正确性 {agg['correctness']:.3f} | "
          f"时效性 {agg['timeliness']:.3f} | 引用 {agg['citation']:.3f} | 综合 {agg['overall']:.3f}")
    if traps:
        print(f"陷阱题({len(traps)}道)：时效 {agg['trap_timeliness']:.3f} 忠实 {agg['trap_faithfulness']:.3f}")
    print(f"含幻觉的题：{agg['n_hallucination_qs']}/{agg['n']}")
    print("=" * 60)
    print(f"\n✅ 明细 → out/generation_metrics.json\n✅ 报告 → {rp}")


def write_report(agg, details, args):
    lines = ["# 生成层评测报告（端到端答案质量）\n"]
    lines.append(f"- 评测集：`gold.jsonl`（{agg['n']} 题）")
    lines.append(f"- 检索配置：{args.mode}"
                 f"{'+rerank' if args.rerank else ''}{'+expand' if args.expand else ''}"
                 f"，alpha={args.alpha}{'，仅现行有效' if args.only_current else ''}")
    lines.append(f"- 生成模型：`{args.gen_model}`｜裁判模型：`{args.judge_model}`（独立更强，避免自评）\n")
    lines.append("## 一、四维度均分\n")
    lines.append("| 维度 | 均分 | 说明 |")
    lines.append("|---|---|---|")
    lines.append(f"| 忠实度(无幻觉) | {agg['faithfulness']:.3f} | 论断是否有检索依据 |")
    lines.append(f"| 正确性 | {agg['correctness']:.3f} | 覆盖标准要点比例 |")
    lines.append(f"| 时效性 | {agg['timeliness']:.3f} | 是否基于现行有效 |")
    lines.append(f"| 引用正确性 | {agg['citation']:.3f} | 参考法规真实且相关 |")
    lines.append(f"| **综合** | **{agg['overall']:.3f}** | 四维均值 |")
    lines.append(f"\n含幻觉的题：**{agg['n_hallucination_qs']}/{agg['n']}**\n")

    if "trap_timeliness" in agg:
        lines.append("## 二、陷阱题(时效性/机型)专项\n")
        lines.append(f"- 时效性均分：**{agg['trap_timeliness']:.3f}**  忠实度均分：**{agg['trap_faithfulness']:.3f}**\n")
        lines.append("| 题号 | 类别 | 忠实 | 正确 | 时效 | 引用 | 判定 | 主要扣分点 |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for d in details:
            if d["is_trap"]:
                lines.append(f"| {d['id']} | {d['category']} | {d['faithfulness']:.2f} | "
                             f"{d['correctness']:.2f} | {d['timeliness']:.2f} | {d['citation']:.2f} | "
                             f"{d['verdict']} | {d['reason']} |")
        lines.append("")

    # 低分题(任一维度<0.6 或有幻觉)
    low = [d for d in details if d["hallucinations"] or
           min(d["faithfulness"], d["correctness"], d["timeliness"], d["citation"]) < 0.6]
    lines.append("## 三、需关注的低分题\n")
    if not low:
        lines.append("（无：所有题各维度均 ≥ 0.6 且无幻觉）\n")
    else:
        lines.append("| 题号 | 类别 | 忠实 | 正确 | 时效 | 引用 | 幻觉 | 原因 |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for d in low:
            hal = "；".join(d["hallucinations"][:2]) if d["hallucinations"] else "—"
            lines.append(f"| {d['id']} | {d['category']} | {d['faithfulness']:.2f} | "
                         f"{d['correctness']:.2f} | {d['timeliness']:.2f} | {d['citation']:.2f} | "
                         f"{hal} | {d['reason']} |")
        lines.append("")

    p = os.path.join(OUT, "generation_report.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return p


if __name__ == "__main__":
    main()
