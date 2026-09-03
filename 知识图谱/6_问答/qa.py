# -*- coding: utf-8 -*-
"""
qa.py —— 第⑥步：GraphRAG 端到端法律问答。
把完整检索链(父子分块→hybrid→时效过滤→rerank→图多跳扩展)召回的
【主命中条文 + 关联条款】喂给 LLM，生成**带法条引用**的答案。

检索复用 5_向量库/search.py 的 retrieve()（无需重复实现召回逻辑）。
LLM 走 OpenAI 兼容接口，沿用 Phase2 的环境变量约定：
  LLM_API_KEY、LLM_BASE_URL(默认 https://open.bigmodel.cn/api/paas/v4)、LLM_MODEL(默认 glm-4-flash)
  智谱 GLM-4-Flash 永久免费；如换 SiliconFlow/DeepSeek 改 LLM_BASE_URL/LLM_MODEL 即可。

用法：
  pip install openai
  set LLM_API_KEY=sk-xxx                         # 生成端(默认智谱GLM-4-Flash,永久免费)
  set SILICONFLOW_API_KEY=sk-yyy                 # 检索端(BGE-M3/rerank)，--mode sparse 时可免
  # 完整链(推荐)：hybrid + rerank + 图扩展 + 仅现行有效
  python qa.py --query "微型无人机需要实名登记吗？" --rerank --expand --only-current --neo4j-pwd 12345678
  # 免 SiliconFlow key 的降级链：纯 BM25 + 图扩展
  python qa.py --query "..." --mode sparse --expand --only-current --neo4j-pwd 12345678
  --show-context  只打印喂给 LLM 的检索上下文，不调生成模型(省 key，验证检索)
"""
import os, sys, json, argparse
sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "5_向量库"))
import search as se   # 复用 retrieve()/检索链

SYSTEM = """你是低空经济无人机领域的中国法律问答助手。依据【检索到的法律条文】回答用户问题。
你的任务是把检索到的多条规定**融会贯通后，用通俗连贯的语言总结成一段友好的回答**。

# 输出格式（严格遵守）
- 用自然、易懂的语言给出**一段总结式回答**，直接说明相关规定是什么、如何适用于用户的问题，让非专业用户也能看懂。
- **不要逐条罗列条文，不要出现具体条号（如"第X条""第X款"），也不要整段照抄条文原文**——用你自己的话概括规定的要点。
- 涉及无人机分类(微型/轻型/小型/中型/大型)时，说清各自的重量/性能界限与义务差异。
- 在回答的**最后另起一行**，用一句话列出本回答参考了哪些法规，只列**法规名称**（去重、加书名号，不带条号），格式：
  「参考法规：《XX法》《YY条例》《ZZ规定》」

# 硬性要求
1. **只依据给定条文作答**，不得臆造或编造法规内容；检索材料不足以回答时，明确说"根据现有检索资料无法确认"，不要猜测。
2. 内部推理时**优先采用现行有效的规定**；对标注[已废止]/[已修改]/[未生效]的条文，不得作为现行有效依据（可忽略，或仅在确有必要时一句话提示其已失效），但**不要在答案里逐条讨论条文状态**。
3. "关联条款"是通过知识图谱扩展出的相关规定(引用/同主体/同机型)，可作补充参考，相关性次于"主要条文"。
4. 全程用中文，语气专业而友好。精确的条号与条文原文用户可在"引用来源"中另行查看，正文无需给出。"""


def build_context(res):
    """把 retrieve() 结果拼成给 LLM 的检索上下文文本。"""
    lines = []
    lines.append("=== 主要条文(向量+关键词召回) ===")
    for i, h in enumerate(res["hits"], 1):
        flag = "" if h.get("时效性") == "现行有效" else f"[{h.get('时效性')}]"
        # 优先用 parent 全文(首次出现)，否则用 child 片段
        body = h.get("parent_text") or h.get("child") or ""
        src = h["head"] if h["is_article"] else f'{h["法规名"]}｜{h["head"]}'
        lines.append(f"\n[{i}] {flag}{src}\n{body.strip()}")

    if res.get("expansion"):
        lines.append("\n\n=== 关联条款(知识图谱多跳扩展) ===")
        for j, d in enumerate(res["expansion"], 1):
            flag = "" if d.get("时效性") == "现行有效" else f"[{d.get('时效性')}]"
            vias = "，".join(d.get("vias", [])[:2])
            lines.append(f"\n[关联{j}] {flag}《{d.get('法规名')}》{d.get('条号') or ''}"
                         f"（{vias}）\n{(d.get('条文') or '').strip()}")
    return "\n".join(lines)


def build_messages(context, query):
    """拼 system+user 消息(CLI 与 web SSE 共用)。"""
    user = (f"【用户问题】{query}\n\n【检索到的法律条文】\n{context}\n\n"
            f"请把上述规定融会贯通，用通俗连贯的语言总结成一段友好的回答，"
            f"不要出现具体条号、不要照抄条文原文；最后一行用"
            f"「参考法规：《…》《…》」列出参考的法规名称（去重、不带条号）。")
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": user}]


def get_llm_client():
    """生成端 OpenAI 兼容客户端。缺 key 抛 RuntimeError(web 捕获，CLI 转 exit)。"""
    from openai import OpenAI
    key = os.environ.get("LLM_API_KEY")
    base = os.environ.get("LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    if not key:
        raise RuntimeError("生成端未设置 LLM_API_KEY 环境变量")
    return OpenAI(api_key=key, base_url=base)


def stream_answer(context, query, model):
    """流式生成答案，逐段 yield token 文本。CLI 与 web SSE 共用。"""
    client = get_llm_client()
    r = client.chat.completions.create(
        model=model, temperature=0.2, stream=True,
        messages=build_messages(context, query),
    )
    for chunk in r:
        piece = chunk.choices[0].delta.content or ""
        if piece:
            yield piece


def generate(context, query, model):
    """调 LLM 生成带引用的答案(CLI：流式打印到 stdout)。"""
    try:
        buf = []
        for piece in stream_answer(context, query, model):
            buf.append(piece)
            print(piece, end="", flush=True)
        print()
        return "".join(buf)
    except RuntimeError as e:
        sys.exit(f"✗ {e}(如需只看检索上下文用 --show-context)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    # 检索参数(透传 search.retrieve)
    ap.add_argument("--mode", choices=["hybrid", "dense", "sparse"], default="hybrid")
    ap.add_argument("--topk", type=int, default=6, help="喂给 LLM 的主命中条文数")
    ap.add_argument("--cand", type=int, default=50)
    ap.add_argument("--alpha", type=float, default=0.5)
    ap.add_argument("--only-current", action="store_true", help="只检索现行有效")
    ap.add_argument("--rerank", action="store_true")
    ap.add_argument("--rerank-n", type=int, default=30)
    ap.add_argument("--rerank-model", default=se.RERANK_MODEL)
    ap.add_argument("--expand", action="store_true", help="图多跳扩展关联条款")
    ap.add_argument("--expand-per", type=int, default=5)
    ap.add_argument("--expand-max", type=int, default=10)
    ap.add_argument("--neo4j-pwd")
    ap.add_argument("--key", help="SiliconFlow key(检索端);默认取 SILICONFLOW_API_KEY")
    # 生成参数
    ap.add_argument("--model", default=os.environ.get("LLM_MODEL", "glm-4-flash"))
    ap.add_argument("--show-context", action="store_true", help="只打印检索上下文,不调生成模型")
    args = ap.parse_args()

    res = se.retrieve(args)
    context = build_context(res)

    if args.show_context:
        print(f"\n【问题】{args.query}\n" + "=" * 70)
        print(context)
        print("\n" + "=" * 70)
        print(f"主命中 {len(res['hits'])} 条｜关联条款 {len(res['expansion'])} 条"
              f"（--show-context 模式，未调用生成模型）")
        return

    tail = (" +rerank" if res["reranked"] else "") + (" +图扩展" if args.expand else "")
    print(f"\n【问题】{args.query}  (检索:{args.mode}{tail}"
          + ("｜仅现行有效" if args.only_current else "") + ")")
    print(f"（主命中 {len(res['hits'])} 条 + 关联 {len(res['expansion'])} 条 → {args.model}）")
    print("=" * 70)
    generate(context, args.query, args.model)


if __name__ == "__main__":
    main()
