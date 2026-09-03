# -*- coding: utf-8 -*-
"""
build_llm_extract.py —— 步骤④：LLM 抽取（本体约束 + 受控词表 + 强制JSON）。
对每个条款单元抽：术语/机型/主体/场景/罚则 + 适用于/义务主体/违反后果。

模型：OpenAI 兼容接口（DeepSeek / Qwen / Moonshot / 本地Ollama 均可）。
  环境变量：LLM_API_KEY、LLM_BASE_URL（如 https://api.deepseek.com）、LLM_MODEL（如 deepseek-chat）
  或用命令行 --base-url / --model 覆盖。
断点续跑：out/llm_cache.jsonl（按 unit_id 去重，可反复跑补齐）。

用法：
  pip install openai
  set LLM_API_KEY=sk-xxx  &  set LLM_BASE_URL=https://api.deepseek.com  &  set LLM_MODEL=deepseek-chat
  python build_llm_extract.py --limit 20      # 先小样验证
  python build_llm_extract.py                 # 全量
  python build_llm_extract.py --aggregate     # 只把cache汇总成 entities/edges（不调API）
"""
import os, sys, re, json, argparse, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from vocab import (DRONE_CATEGORIES, SPECIAL_CATEGORIES, ACTOR_SEEDS,
                   ACTIVITY_SEEDS, SANCTION_TYPES, canon)

IN = os.path.join(os.path.dirname(HERE), "1_结构化", "out", "units_normalized.json")
OUT = os.path.join(HERE, "out")
CACHE = os.path.join(OUT, "llm_cache.jsonl")

DRONE_ENUM = list(DRONE_CATEGORIES.keys()) + list(SPECIAL_CATEGORIES.keys())

SYSTEM = f"""你是法律知识图谱的实体关系抽取器。从给定的【条文】中，严格按本体抽取，只输出JSON。

受控词表（优先归入，无法归入才新增并在值后加"*"）：
- 机型(只能取)：{DRONE_ENUM}
- 主体(优先)：{ACTOR_SEEDS}
- 场景(优先)：{ACTIVITY_SEEDS}
- 罚则类型(只能取)：{SANCTION_TYPES}

抽取规则：
- 术语：仅当条文以"XX，是指/所称XX是指"给出定义时抽，返回{{术语名,定义}}；只是提及不算。
- 机型：条文明确限定某机型或给出重量/性能阈值时抽；泛指"无人驾驶航空器"(未限定)不抽。
- 主体：负有义务或行使职权的主体；泛称"任何单位和个人"照写。
- 场景：受该条约束的行为/活动。
- 罚则：出现"处…罚款/责令改正/吊销/追究刑事责任"等时抽，返回{{类型,额度,描述}}。
- 引用：条文出现的"第X条""《法规名》第X条"（兜底，正则已抽，可少填）。
只依据条文本身，不臆造。无内容的字段返回空数组。"""

SCHEMA_HINT = """输出JSON格式：
{"术语":[{"术语名":"","定义":""}],"机型":[],"主体":[],"场景":[],"罚则":[{"类型":"","额度":"","描述":""}],"引用":[]}"""


def build_user(u):
    ctx = f"【法规】{u.get('法规名')}　【条号】{u.get('条号') or u.get('unit_type')}"
    return f"{ctx}\n【条文】{u.get('条文')}\n\n{SCHEMA_HINT}"


def get_client():
    from openai import OpenAI
    key = os.environ.get("LLM_API_KEY")
    base = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com")
    if not key:
        sys.exit("✗ 未设置 LLM_API_KEY 环境变量")
    return OpenAI(api_key=key, base_url=base)


def extract_one(client, model, u):
    r = client.chat.completions.create(
        model=model, temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": build_user(u)}],
    )
    data = json.loads(r.choices[0].message.content)
    data["unit_id"] = u["unit_id"]
    return data


def load_done():
    done = set()
    if os.path.exists(CACHE):
        for ln in open(CACHE, encoding="utf-8"):
            try:
                done.add(json.loads(ln)["unit_id"])
            except Exception:
                pass
    return done


def aggregate():
    """把 cache 汇总成 实体表 + 语义边（适用于/义务主体/违反后果），并过 vocab.canon 归一。"""
    ents = {"Term": {}, "DroneCategory": {}, "Actor": {}, "Activity": {}, "Sanction": []}
    edges = []
    sid = 0

    def as_name(x, *keys):
        """把元素规整为名称字符串——LLM 偶尔把机型/主体/场景返回成 dict。"""
        if isinstance(x, dict):
            for k in (keys or ("名称", "name", "术语名")):
                if x.get(k):
                    x = x[k]
                    break
            else:
                x = next((v for v in x.values() if isinstance(v, str) and v), "")
        return str(x).strip().rstrip("*").strip() if x else ""

    for ln in open(CACHE, encoding="utf-8"):
        d = json.loads(ln)
        uid = d["unit_id"]
        for t in d.get("术语", []):
            nm = as_name(t, "术语名") if isinstance(t, dict) else as_name(t)
            defi = t.get("定义") if isinstance(t, dict) else None
            if nm:
                ents["Term"].setdefault(nm, {"id": nm, "术语名": nm, "定义": defi})
                edges.append({"src": uid, "rel": "定义", "dst": nm})
        for m in d.get("机型", []):
            m2 = canon(as_name(m))
            if not m2:
                continue
            ents["DroneCategory"].setdefault(m2, {"id": m2})
            edges.append({"src": uid, "rel": "适用于", "dst": m2, "类别": "机型"})
        for a in d.get("主体", []):
            a2 = canon(as_name(a))
            if not a2:
                continue
            ents["Actor"].setdefault(a2, {"id": a2})
            edges.append({"src": uid, "rel": "义务主体", "dst": a2})
        for s in d.get("场景", []):
            s2 = canon(as_name(s))
            if not s2:
                continue
            ents["Activity"].setdefault(s2, {"id": s2})
            edges.append({"src": uid, "rel": "适用于", "dst": s2, "类别": "场景"})
        for p in d.get("罚则", []):
            if not isinstance(p, dict):
                continue
            sid += 1
            pid = f"sanction_{sid}"
            ents["Sanction"].append({"id": pid, **p})
            edges.append({"src": uid, "rel": "违反后果", "dst": pid})
    ents["Term"] = list(ents["Term"].values())
    ents["DroneCategory"] = list(ents["DroneCategory"].values())
    ents["Actor"] = list(ents["Actor"].values())
    ents["Activity"] = list(ents["Activity"].values())
    json.dump(ents, open(os.path.join(OUT, "nodes_llm.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump(edges, open(os.path.join(OUT, "edges_llm.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"✅ 汇总：术语{len(ents['Term'])} 机型{len(ents['DroneCategory'])} 主体{len(ents['Actor'])} "
          f"场景{len(ents['Activity'])} 罚则{len(ents['Sanction'])}｜语义边 {len(edges)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--model", default=os.environ.get("LLM_MODEL", "deepseek-chat"))
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--aggregate", action="store_true")
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    if args.aggregate:
        return aggregate()

    if args.base_url:
        os.environ["LLM_BASE_URL"] = args.base_url
    units = json.load(open(IN, encoding="utf-8"))
    done = load_done()
    todo = [u for u in units if u["unit_id"] not in done]
    if args.limit:
        todo = todo[:args.limit]
    print(f"待抽取 {len(todo)}（已完成 {len(done)}），模型 {args.model}")

    client = get_client()
    lock = threading.Lock()
    fout = open(CACHE, "a", encoding="utf-8")
    ok = err = 0

    def work(u):
        nonlocal ok, err
        try:
            data = extract_one(client, args.model, u)
            with lock:
                fout.write(json.dumps(data, ensure_ascii=False) + "\n"); fout.flush()
                ok += 1
                if ok % 50 == 0:
                    print(f"  ...{ok} done")
        except Exception as e:
            with lock:
                err += 1
                if err <= 5:
                    print(f"  ✗ {u['unit_id']}: {str(e)[:80]}")

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        list(as_completed([ex.submit(work, u) for u in todo]))
    fout.close()
    print(f"完成 ok={ok} err={err}。运行 --aggregate 汇总为 nodes_llm/edges_llm。")


if __name__ == "__main__":
    main()
