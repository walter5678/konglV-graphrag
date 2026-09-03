# -*- coding: utf-8 -*-
"""
build_chunks.py —— 向量库 Phase5 第一步：父子分块(parent-child chunking)。

策略(基于真实数据：条文中位102字，仅62条>600字，60条带款)：
  Parent = 检索命中后返回给 LLM 的完整上下文单元
  Child  = 真正拿去 embedding 的小块，命中后回溯其 parent
  - 法条(Article)：parent=整条条文；child=① 带款长条→逐款切 ② 其余→整条为一块，超长滑窗切
  - 案例(Case)   ：parent=判决摘要；child=标题+案由+摘要(滑窗)，让"案由/纠纷类型"可检索
关键连接：parent_id 对齐图节点 id(法条=unit_id，案例=cli)，向量命中后可直接跳进 Neo4j 图多跳扩展。
embedding 文本拼 `《法规名》条号` / `标题｜案由` 前缀提升召回；raw 存原文供展示。

输入：
  1_结构化/out/units_normalized.json   3701 法条单元
  4_案例/out/nodes_cases.json          531 Case 节点
输出(5_向量库/out/)：
  parents.json    {parent_id: {text, 法规名, 条号, node_type, 元数据...}}
  children.jsonl  每行一个 child：{child_id, parent_id, embed_text, raw, 过滤元数据}
  stats.json
"""
import os, re, sys, json
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
KG = os.path.dirname(HERE)
UNITS = os.path.join(KG, "1_结构化", "out", "units_normalized.json")
CASES = os.path.join(KG, "4_案例", "out", "nodes_cases.json")
OUT = os.path.join(HERE, "out")

WINDOW = 350      # 滑窗字数(超长块)
OVERLAP = 60      # 相邻窗重叠
MIN_CHILD = 8     # 过短片段并入上一块
SENT_END = "。；！？"


def split_sentences(text):
    """按句末标点切句，保留标点。"""
    out, buf = [], ""
    for ch in text:
        buf += ch
        if ch in SENT_END:
            out.append(buf.strip()); buf = ""
    if buf.strip():
        out.append(buf.strip())
    return [s for s in out if s]


def window_split(text):
    """长文本按句子聚成 ~WINDOW 字的窗口，带 OVERLAP 重叠。"""
    sents = split_sentences(text)
    if not sents:
        return [text] if text.strip() else []
    chunks, cur = [], ""
    for s in sents:
        if cur and len(cur) + len(s) > WINDOW:
            chunks.append(cur)
            # 重叠：从 cur 尾部回退 OVERLAP 字接续
            tail = cur[-OVERLAP:] if len(cur) > OVERLAP else ""
            cur = tail + s
        else:
            cur += s
    if cur.strip():
        chunks.append(cur.strip())
    return chunks


def article_children(text, kuan):
    """法条切 child：带款(>1)长条→逐款；否则整条，超长滑窗。"""
    text = (text or "").strip()
    kuan = [k.strip() for k in (kuan or []) if k and k.strip()]
    if len(kuan) > 1 and len("".join(kuan)) > 400:
        # 逐款为 child，过短的款并入前一块
        childs = []
        for k in kuan:
            if childs and len(k) < MIN_CHILD * 4:
                childs[-1] += k
            elif len(k) > WINDOW * 1.5:
                childs.extend(window_split(k))
            else:
                childs.append(k)
        return childs
    if len(text) <= WINDOW * 1.5:
        return [text] if text else []
    return window_split(text)


def main():
    os.makedirs(OUT, exist_ok=True)
    units = json.load(open(UNITS, encoding="utf-8"))
    cases = json.load(open(CASES, encoding="utf-8")) if os.path.exists(CASES) else []

    parents = {}
    children = []
    ntype_c = Counter()
    child_per_parent = []

    # ---- 法条 ----
    for u in units:
        text = (u.get("条文") or "").strip()
        if not text:
            continue
        pid = u["unit_id"]
        law, tiao = u.get("法规名") or "", u.get("条号") or ""
        parents[pid] = {
            "parent_id": pid, "node_type": "Article", "text": text,
            "法规名": law, "条号": tiao, "章": u.get("章"), "节": u.get("节"),
            "law_id": u.get("law_id"),
            "效力层级": u.get("效力层级"), "效力rank": u.get("效力rank"),
            "时效性": u.get("时效性"), "来源": u.get("来源"),
        }
        prefix = f"《{law}》{tiao}".strip("《》 ")
        ch = article_children(text, u.get("款"))
        child_per_parent.append(len(ch))
        for i, c in enumerate(ch):
            children.append({
                "child_id": f"{pid}#c{i}", "parent_id": pid, "node_type": "Article",
                "embed_text": (f"《{law}》{tiao}\n{c}" if law else c),
                "raw": c,
                "法规名": law, "条号": tiao, "效力层级": u.get("效力层级"),
                "时效性": u.get("时效性"), "来源": u.get("来源"),
            })
        ntype_c["Article"] += 1

    # ---- 案例 ----
    for c in cases:
        summary = (c.get("判决摘要") or "").strip()
        title = c.get("标题") or ""
        cause = c.get("案由") or ""
        # parent 文本：摘要为主，空则用标题+案由兜底
        ptext = summary or f"{title}\n案由：{cause}"
        pid = c["id"]
        parents[pid] = {
            "parent_id": pid, "node_type": "Case", "text": ptext,
            "标题": title, "案由": cause, "案号": c.get("案号"),
            "审理法院": c.get("审理法院"), "文书类型": c.get("文书类型"),
            "相关企业": c.get("相关企业"), "审理年份": c.get("审理年份"),
            "时效性": c.get("时效性"),
        }
        ctx = f"{title}｜案由:{cause}"
        pieces = window_split(summary) if len(summary) > WINDOW * 1.5 else ([summary] if summary else [])
        if not pieces:
            pieces = [""]
        child_per_parent.append(len(pieces))
        for i, p in enumerate(pieces):
            children.append({
                "child_id": f"{pid}#c{i}", "parent_id": pid, "node_type": "Case",
                "embed_text": f"{ctx}\n{p}".strip(),
                "raw": p or ctx,
                "法规名": None, "条号": None, "效力层级": "司法案例",
                "时效性": c.get("时效性"), "来源": "pkulaw",
                "文书类型": c.get("文书类型"), "审理法院": c.get("审理法院"),
            })
        ntype_c["Case"] += 1

    json.dump(parents, open(os.path.join(OUT, "parents.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    with open(os.path.join(OUT, "children.jsonl"), "w", encoding="utf-8") as f:
        for c in children:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    elens = [len(c["embed_text"]) for c in children]
    stats = {
        "parent数": len(parents), "child数": len(children),
        "parent按类型": dict(ntype_c),
        "平均child/parent": round(sum(child_per_parent) / max(len(child_per_parent), 1), 2),
        "拆出多child的parent数": sum(1 for n in child_per_parent if n > 1),
        "embed_text长度": {"中位": sorted(elens)[len(elens) // 2] if elens else 0,
                          "最大": max(elens) if elens else 0,
                          ">512字块数": sum(1 for l in elens if l > 512)},
    }
    json.dump(stats, open(os.path.join(OUT, "stats.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"✅ 分块完成：parent {len(parents)} | child {len(children)}")
    print(f"   parent类型 {dict(ntype_c)}｜平均 {stats['平均child/parent']} child/parent"
          f"｜拆多块parent {stats['拆出多child的parent数']}")
    print(f"   embed_text 中位 {stats['embed_text长度']['中位']}字 最大 {stats['embed_text长度']['最大']}字"
          f" >512字块 {stats['embed_text长度']['>512字块数']}")


if __name__ == "__main__":
    main()
