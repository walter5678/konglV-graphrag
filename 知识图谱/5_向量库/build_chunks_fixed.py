# -*- coding: utf-8 -*-
"""
build_chunks_fixed.py —— 对照分块方法 B：固定长度滑窗分块(fixed-size sliding window)。

这是"朴素 RAG"最常见的默认切分：把文本按固定字数切成等长窗口、相邻窗重叠，
**完全不理会法条边界**——一个窗口可以跨两条条文，一条短条文也可能被邻条吞没。
本脚本作为父子分块(build_chunks.py，方法 A)的对照基线，用于第 6 章分块方法对比：
在同一 parents.json、同一 BM25 检索器、同一 gold 上，仅替换 child 切分方式，
隔离"分块策略"这一单一变量，量化其对检索指标的影响。

与方法 A 的唯一差异在 child 切法：
  A(父子)：child 尊重法条/款边界，短条整条为一块，长条逐款/滑窗。
  B(固定)：把同一部法规的条文按顺序拼成连续文本流，按 WINDOW 字硬切、OVERLAP 重叠，
           跨条不停顿；每个窗口的 parent_id = 该窗口内**占字符最多的那条**(多数归属)。

parent_id 仍对齐图节点 id(=unit_id / cli)，直接复用 build_chunks.py 产出的 parents.json，
故命中可照常回溯父块全文、并与 gold_parent_ids 比对。

输出(5_向量库/out/)：
  children_fixed.jsonl   固定窗口 child，schema 与 children.jsonl 完全一致
  stats_fixed.json
"""
import os, sys, json
from collections import Counter, defaultdict
sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
KG = os.path.dirname(HERE)
UNITS = os.path.join(KG, "1_结构化", "out", "units_normalized.json")
CASES = os.path.join(KG, "4_案例", "out", "nodes_cases.json")
OUT = os.path.join(HERE, "out")

WINDOW = 350      # 与方法 A 的滑窗字数一致，保证公平：只变"是否尊重法条边界"
OVERLAP = 60      # 相邻窗重叠


def sliding_windows(stream_len, window, overlap):
    """在长度 stream_len 上生成 [start, end) 窗口区间，步长 window-overlap。"""
    step = max(window - overlap, 1)
    spans, start = [], 0
    while start < stream_len:
        end = min(start + window, stream_len)
        spans.append((start, end))
        if end >= stream_len:
            break
        start += step
    return spans


def majority_owner(char_owner, s, e):
    """窗口 [s,e) 内出现字符最多的 parent_id(多数归属)。"""
    c = Counter(char_owner[s:e])
    return c.most_common(1)[0][0] if c else None


def chunk_law_stream(law_units):
    """把一部法规的条文按条号顺序拼成连续字符流，固定滑窗切块。
    返回 [(parent_id, window_text)]。跨条不停顿——刻意制造"窗口跨条"的朴素缺陷。"""
    stream_chars, char_owner = [], []
    for u in law_units:
        text = (u.get("条文") or "").strip()
        if not text:
            continue
        pid = u["unit_id"]
        for ch in text:
            stream_chars.append(ch)
            char_owner.append(pid)
        # 条间用换行分隔(也计入字符流)，模拟真实拼接文本
        stream_chars.append("\n")
        char_owner.append(pid)
    stream = "".join(stream_chars)
    out = []
    for s, e in sliding_windows(len(stream), WINDOW, OVERLAP):
        seg = stream[s:e].strip()
        if not seg:
            continue
        owner = majority_owner(char_owner, s, e)
        out.append((owner, seg))
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    units = json.load(open(UNITS, encoding="utf-8"))
    cases = json.load(open(CASES, encoding="utf-8")) if os.path.exists(CASES) else []

    # 建 unit_id → 元数据 与 分法规分组(保序)
    umeta = {}
    by_law = defaultdict(list)
    for u in units:
        if not (u.get("条文") or "").strip():
            continue
        umeta[u["unit_id"]] = u
        by_law[u.get("law_id") or u.get("法规名") or "_"].append(u)

    children = []
    covered = set()          # 被至少一个窗口"多数拥有"的 article parent
    all_articles = set(umeta)

    # ---- 法条：按法规流式固定窗口 ----
    for law_id, law_units in by_law.items():
        for owner, seg in chunk_law_stream(law_units):
            if owner is None:
                continue
            u = umeta[owner]
            law = u.get("法规名") or ""
            idx = sum(1 for c in children if c["parent_id"] == owner)
            children.append({
                "child_id": f"{owner}#f{idx}", "parent_id": owner, "node_type": "Article",
                # 固定窗口跨条，条号不确定 → 只挂法规名前缀(方法 A 是《法规名》条号)
                "embed_text": (f"《{law}》\n{seg}" if law else seg),
                "raw": seg,
                "法规名": law, "条号": u.get("条号") or "", "效力层级": u.get("效力层级"),
                "时效性": u.get("时效性"), "来源": u.get("来源"),
            })
            covered.add(owner)

    # ---- 案例：判决摘要同样固定窗口 ----
    for c in cases:
        summary = (c.get("判决摘要") or "").strip()
        title = c.get("标题") or ""
        cause = c.get("案由") or ""
        pid = c["id"]
        text = summary or f"{title}\n案由：{cause}"
        spans = sliding_windows(len(text), WINDOW, OVERLAP)
        for i, (s, e) in enumerate(spans):
            seg = text[s:e].strip()
            if not seg:
                continue
            children.append({
                "child_id": f"{pid}#f{i}", "parent_id": pid, "node_type": "Case",
                "embed_text": seg, "raw": seg,
                "法规名": None, "条号": None, "效力层级": "司法案例",
                "时效性": c.get("时效性"), "来源": "pkulaw",
                "文书类型": c.get("文书类型"), "审理法院": c.get("审理法院"),
            })

    out_path = os.path.join(OUT, "children_fixed.jsonl")
    with open(out_path, "w", encoding="utf-8") as f:
        for c in children:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    # 关键缺陷量化：有多少法条因过短/被邻条吞没，从未成为任一窗口的"多数拥有者"
    orphan = all_articles - covered
    elens = [len(c["embed_text"]) for c in children]
    stats = {
        "child数": len(children),
        "覆盖article数": len(covered),
        "article总数": len(all_articles),
        "未被任何窗口多数拥有的article数(检索不可达)": len(orphan),
        "孤儿占比": round(len(orphan) / max(len(all_articles), 1), 4),
        "embed_text长度": {"中位": sorted(elens)[len(elens) // 2] if elens else 0,
                          "最大": max(elens) if elens else 0},
    }
    json.dump(stats, open(os.path.join(OUT, "stats_fixed.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"✅ 固定窗口分块完成：child {len(children)} → {out_path}")
    print(f"   覆盖 article {len(covered)}/{len(all_articles)}"
          f"｜孤儿(检索不可达) {len(orphan)} 条 ({stats['孤儿占比']*100:.1f}%)")
    print(f"   embed_text 中位 {stats['embed_text长度']['中位']}字 最大 {stats['embed_text长度']['最大']}字")


if __name__ == "__main__":
    main()
