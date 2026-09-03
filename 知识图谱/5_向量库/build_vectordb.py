# -*- coding: utf-8 -*-
"""
build_vectordb.py —— 向量库 Phase5 第二步：child 嵌入 → Chroma 独立向量库。

- 嵌入：SiliconFlow 的 BAAI/bge-m3(OpenAI 兼容 /v1/embeddings)，1024维。
  key 取环境变量 SILICONFLOW_API_KEY(或 --key)。base_url 默认 https://api.siliconflow.cn/v1。
- 向量库：Chroma 持久化到 5_向量库/chroma_db/，collection=drone_law。
  只存 child 向量 + 过滤元数据(法规名/条号/效力层级/时效性/来源/node_type/parent_id)。
  parent 全文存 parents.json 边车(命中 child 后按 parent_id 回溯)——父子分块。
- 断点续跑：已在 collection 里的 child_id 跳过。分批调用 embedding API。

用法：
  set SILICONFLOW_API_KEY=sk-xxx
  python build_vectordb.py                 # 全量建库
  python build_vectordb.py --limit 50      # 小样冒烟
  python build_vectordb.py --query "微型无人机的重量标准"   # 建完后检索测试
"""
import os, sys, json, time, argparse
sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")


def _resolve_db():
    """chroma 的 HNSW 索引由 hnswlib C++ 层写盘，Windows 下无法写非 ASCII(中文)路径，
    段目录会只剩 index_metadata.pickle 而缺 header.bin。项目路径含中文时，
    库落到 ASCII 的用户目录(可用 DRONE_CHROMA_DIR 覆盖)。"""
    env = os.environ.get("DRONE_CHROMA_DIR")
    if env:
        return env
    d = os.path.join(HERE, "chroma_db")
    if os.name == "nt" and not all(ord(c) < 128 for c in d):
        return os.path.join(os.path.expanduser("~"), "drone_law_chroma")
    return d


DB = _resolve_db()
CHILDREN = os.path.join(OUT, "children.jsonl")
PARENTS = os.path.join(OUT, "parents.json")
COLL = "drone_law"
MODEL = "BAAI/bge-m3"
BASE = os.environ.get("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
BATCH = 32        # 每次 embedding API 的文本条数

# Chroma 元数据不接受 None，清洗
def clean_meta(d):
    return {k: ("" if v is None else v) for k, v in d.items()}


def get_client(key):
    from openai import OpenAI
    key = key or os.environ.get("SILICONFLOW_API_KEY")
    if not key:
        sys.exit("✗ 未提供 API key：set SILICONFLOW_API_KEY 或传 --key")
    return OpenAI(api_key=key, base_url=BASE)


def embed_batch(client, texts, retry=4):
    for i in range(retry):
        try:
            r = client.embeddings.create(model=MODEL, input=texts)
            return [d.embedding for d in r.data]
        except Exception as e:
            wait = 2 ** i
            print(f"   ⚠ embedding 失败({str(e)[:60]})，{wait}s 后重试 {i+1}/{retry}")
            time.sleep(wait)
    raise RuntimeError("embedding 连续失败")


def load_children():
    rows = []
    with open(CHILDREN, encoding="utf-8") as f:
        for ln in f:
            rows.append(json.loads(ln))
    return rows


def cmd_build(args):
    import chromadb
    client = get_client(args.key)
    chroma = chromadb.PersistentClient(path=DB)
    if args.reset:
        # child 集合变化(严筛后有增有删)时必须重建，否则旧 collection 残留
        # 已被剔除的 child 向量(孤儿)会污染检索。
        try:
            chroma.delete_collection(COLL)
            print(f"↺ 已删除旧 collection '{COLL}'，将全量重建")
        except Exception:
            pass
    coll = chroma.get_or_create_collection(COLL, metadata={"hnsw:space": "cosine"})

    rows = load_children()
    # children.jsonl 存在重复 child_id(源自 73 个 Article unit_id 重复)，
    # Chroma 同批内遇重复 id 会 DuplicateIDError，按 child_id 去重(保留首个)
    seen_ids, uniq, dup = set(), [], 0
    for r in rows:
        if r["child_id"] in seen_ids:
            dup += 1
            continue
        seen_ids.add(r["child_id"])
        uniq.append(r)
    if dup:
        print(f"⚠ children 内重复 child_id 已去重 {dup} 条 → {len(uniq)} 条")
    rows = uniq
    if args.limit:
        rows = rows[:args.limit]
    done = set(coll.get(include=[])["ids"]) if coll.count() else set()
    todo = [r for r in rows if r["child_id"] not in done]
    print(f"child 总 {len(rows)} | 已入库 {len(done)} | 待嵌入 {len(todo)}｜模型 {MODEL}")
    print(f"   库位置 {DB}")

    ok = 0
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        vecs = embed_batch(client, [r["embed_text"] for r in batch])
        coll.add(
            ids=[r["child_id"] for r in batch],
            embeddings=vecs,
            documents=[r["raw"] for r in batch],
            metadatas=[clean_meta({
                "parent_id": r["parent_id"], "node_type": r["node_type"],
                "法规名": r.get("法规名"), "条号": r.get("条号"),
                "效力层级": r.get("效力层级"), "时效性": r.get("时效性"),
                "来源": r.get("来源"), "文书类型": r.get("文书类型"),
            }) for r in batch],
        )
        ok += len(batch)
        if ok % 320 == 0 or i + BATCH >= len(todo):
            print(f"   ...{ok}/{len(todo)}")
    print(f"✅ 向量库建成：collection '{COLL}' 共 {coll.count()} child 向量 → {DB}")


def cmd_query(args):
    import chromadb
    client = get_client(args.key)
    chroma = chromadb.PersistentClient(path=DB)
    coll = chroma.get_collection(COLL)
    parents = json.load(open(PARENTS, encoding="utf-8"))

    qvec = embed_batch(client, [args.query])[0]
    where = None
    if args.only_current:
        where = {"时效性": "现行有效"}
    res = coll.query(query_embeddings=[qvec], n_results=args.topk,
                     where=where, include=["metadatas", "documents", "distances"])
    print(f"\n查询：{args.query}\n" + "=" * 70)
    seen_parent = set()
    for cid, meta, doc, dist in zip(res["ids"][0], res["metadatas"][0],
                                    res["documents"][0], res["distances"][0]):
        pid = meta["parent_id"]
        tag = "案例" if meta["node_type"] == "Case" else meta.get("法规名", "")
        head = (f"{tag} {meta.get('条号','')}".strip()
                if meta["node_type"] == "Article" else parents.get(pid, {}).get("标题", tag))
        flag = "" if meta.get("时效性") == "现行有效" else f"[{meta.get('时效性')}]"
        print(f"\n● sim={1-dist:.3f} {flag} {head}")
        print(f"  child: {doc[:90]}")
        if pid not in seen_parent:
            seen_parent.add(pid)
            ptext = parents.get(pid, {}).get("text", "")
            print(f"  ↳parent[{pid}]: {ptext[:120]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--reset", action="store_true", help="重建前清空旧 collection(child 集合变动时用)")
    ap.add_argument("--query")
    ap.add_argument("--topk", type=int, default=6)
    ap.add_argument("--only-current", action="store_true", help="只检索现行有效")
    args = ap.parse_args()
    if args.query:
        cmd_query(args)
    else:
        cmd_build(args)


if __name__ == "__main__":
    main()
