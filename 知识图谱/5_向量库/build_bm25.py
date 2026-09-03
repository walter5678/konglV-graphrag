# -*- coding: utf-8 -*-
"""
build_bm25.py —— hybrid 召回第一步：为 children 建 BM25 稀疏索引。

背景：SiliconFlow /v1/embeddings 只给 BGE-M3 稠密向量，拿不到 sparse 权重，
故稀疏侧走本地 BM25(jieba 分词 + rank_bm25)。语料复用 out/children.jsonl，
按 child_id 去重(与 Chroma 里 5131 条对齐)。

- jieba 灌入 2_抽取/vocab.py 领域词表，避免"无人驾驶航空器/适航审定/管制空域飞行"被切碎。
- 索引 pickle 到 out/bm25.pkl(纯 Python，中文路径无碍)：BM25Okapi + child_ids + 元数据快照。

用法：python build_bm25.py
"""
import os, re, sys, json, pickle
sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
KG = os.path.dirname(HERE)
OUT = os.path.join(HERE, "out")
CHILDREN = os.path.join(OUT, "children.jsonl")
BM25_PKL = os.path.join(OUT, "bm25.pkl")

_PUNCT = set("，。；！？、：（）()《》「」“”\"'【】〔〕[]{}\n\r\t 　·…—－-,.;!?:%/\\|＋+=~•")


def tokenize(text):
    """jieba 分词 + 去纯标点/空白 token；保留数字与英文(阈值/缩写有意义)。"""
    import jieba
    toks = jieba.lcut((text or "").strip())
    out = []
    for t in toks:
        t = t.strip()
        if not t or all(ch in _PUNCT for ch in t):
            continue
        out.append(t.lower())
    return out


def load_domain_dict():
    """把 vocab.py 领域词表加入 jieba 自定义词典，返回加载词数。"""
    import jieba
    sys.path.insert(0, os.path.join(KG, "2_抽取"))
    import vocab
    words = set()
    words |= set(vocab.DRONE_CATEGORIES.keys())
    words |= set(vocab.SPECIAL_CATEGORIES.keys())
    words |= set(vocab.ACTOR_SEEDS)
    words |= set(vocab.ACTIVITY_SEEDS)
    words |= set(vocab.SANCTION_TYPES)
    words |= set(vocab.ALIASES.keys())
    words |= set(vocab.ALIASES.values())
    n = 0
    for w in sorted(words):
        if w and len(w) >= 2:
            jieba.add_word(w)
            n += 1
    return n


def load_children_dedup():
    """读 children.jsonl 并按 child_id 去重(保留首个)，与 build_vectordb 一致。"""
    rows, seen, dup = [], set(), 0
    with open(CHILDREN, encoding="utf-8") as f:
        for ln in f:
            r = json.loads(ln)
            if r["child_id"] in seen:
                dup += 1
                continue
            seen.add(r["child_id"])
            rows.append(r)
    return rows, dup


META_KEYS = ["parent_id", "node_type", "法规名", "条号", "效力层级",
             "时效性", "来源", "文书类型"]


def main():
    from rank_bm25 import BM25Okapi
    ndict = load_domain_dict()
    print(f"jieba 领域词典加载 {ndict} 词")

    rows, dup = load_children_dedup()
    if dup:
        print(f"⚠ children 去重 {dup} 条 → {len(rows)} 条")

    print("分词中(jieba)...")
    corpus = [tokenize(r["embed_text"]) for r in rows]
    child_ids = [r["child_id"] for r in rows]
    metas = [{k: r.get(k) for k in META_KEYS} for r in rows]
    raws = [r.get("raw", "") for r in rows]

    bm25 = BM25Okapi(corpus)
    with open(BM25_PKL, "wb") as f:
        pickle.dump({"bm25": bm25, "child_ids": child_ids,
                     "metas": metas, "raws": raws}, f)

    avg = sum(len(c) for c in corpus) / max(len(corpus), 1)
    print(f"✅ BM25 索引建成：{len(child_ids)} child | 平均 {avg:.1f} token/child → {BM25_PKL}")


if __name__ == "__main__":
    main()
