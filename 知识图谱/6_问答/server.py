# -*- coding: utf-8 -*-
"""
server.py —— GraphRAG 无人机法律问答的 Web 后端(FastAPI + SSE 流式)。

复用检索链(5_向量库/search.retrieve)与生成端(qa.stream_answer)，把 CLI 能力
包成 HTTP 服务，配合 static/index.html 的 GPT 风格前端。

接口：
  GET  /              → 前端页面(static/index.html)
  GET  /api/health    → 健康检查 + 各依赖(向量库key/Neo4j/生成key)就绪状态
  POST /api/chat      → SSE 流式问答。请求体 JSON:
       {query, mode?, only_current?, rerank?, expand?, topk?, expand_max?}
       SSE 事件: meta(检索来源) → token(逐段答案) → done / error

密钥走环境变量(不写盘)：
  SILICONFLOW_API_KEY  检索端 BGE-M3/rerank(mode=sparse 时可免)
  LLM_API_KEY / LLM_BASE_URL / LLM_MODEL   生成端
       默认 智谱GLM-4-Flash(永久免费): base=https://open.bigmodel.cn/api/paas/v4, model=glm-4-flash
  NEO4J_PASSWORD       图扩展(默认 12345678)

启动：
  set SILICONFLOW_API_KEY=sk-xxx           # 检索端(hybrid/dense/rerank 需要)
  set LLM_API_KEY=zhipu-key                 # 生成端(智谱开放平台 key)
  python server.py                 # 默认 http://127.0.0.1:8000，生成走 GLM-4-Flash
  python server.py --port 8080 --host 0.0.0.0
"""
import os, sys, json, argparse
from types import SimpleNamespace
sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "5_向量库"))

import search as se
import qa

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

STATIC = os.path.join(HERE, "static")
DEFAULT_MODEL = os.environ.get("LLM_MODEL", "glm-4-flash")

app = FastAPI(title="低空经济无人机法律智能问答")


def build_args(body):
    """把前端请求体转成 search.retrieve() 需要的 args 对象。"""
    mode = body.get("mode", "hybrid")
    return SimpleNamespace(
        query=body["query"].strip(),
        mode=mode if mode in ("hybrid", "dense", "sparse") else "hybrid",
        topk=int(body.get("topk", 6)),
        cand=50,
        alpha=0.5,
        only_current=bool(body.get("only_current", True)),
        rerank=bool(body.get("rerank", True)),
        rerank_n=30,
        rerank_model=se.RERANK_MODEL,
        expand=bool(body.get("expand", True)),
        expand_per=5,
        expand_max=int(body.get("expand_max", 6)),
        neo4j_pwd=os.environ.get("NEO4J_PASSWORD", "12345678"),
        key=os.environ.get("SILICONFLOW_API_KEY"),
    )


def sse(event, data):
    """格式化一条 SSE 消息。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def hits_payload(res):
    """检索结果 → 前端可展示的来源列表(主命中 + 关联条款)。"""
    main = [{
        "type": "case" if h.get("node_type") == "Case" else "article",
        "law": h.get("法规名", ""), "art": h.get("条号", ""),
        "head": h.get("head", ""), "status": h.get("时效性", ""),
        "score": round(float(h.get("score", 0)), 4),
        "text": (h.get("parent_text") or h.get("child") or "")[:600],
    } for h in res["hits"]]
    linked = [{
        "law": d.get("法规名", ""), "art": d.get("条号", ""),
        "status": d.get("时效性", ""),
        "via": "，".join(d.get("vias", [])[:2]),
        "seeds": len(d.get("from_seeds", [])),
        "text": (d.get("条文") or "")[:600],
    } for d in res.get("expansion", [])]
    return {"main": main, "linked": linked}


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "retrieval_key": bool(os.environ.get("SILICONFLOW_API_KEY")),
        "generation_key": bool(os.environ.get("LLM_API_KEY")),
        "model": DEFAULT_MODEL,
        "neo4j_pwd_set": bool(os.environ.get("NEO4J_PASSWORD")),
    }


@app.post("/api/chat")
async def chat(request: Request):
    body = await request.json()
    if not (body.get("query") or "").strip():
        return JSONResponse({"error": "问题不能为空"}, status_code=400)
    args = build_args(body)
    model = body.get("model") or DEFAULT_MODEL

    def stream():
        # ① 检索(阻塞) → 先把来源发给前端
        try:
            res = se.retrieve(args)
        except SystemExit as e:      # dense/rerank 缺 SiliconFlow key 时 get_key 会 sys.exit
            yield sse("error", {"message": f"检索失败：{e}。dense/rerank 需 SILICONFLOW_API_KEY，或改用 sparse 模式。"})
            return
        except Exception as e:
            yield sse("error", {"message": f"检索失败：{str(e)[:200]}"})
            return
        yield sse("meta", {
            "mode": res["mode"], "reranked": res["reranked"],
            "only_current": res["only_current"],
            "n_main": len(res["hits"]), "n_linked": len(res["expansion"]),
            "sources": hits_payload(res),
        })
        if not res["hits"]:
            yield sse("token", {"text": "抱歉，未检索到相关法律条文。请换个说法或缩小范围再试。"})
            yield sse("done", {})
            return
        # ② 生成(流式) → 逐段 token
        context = qa.build_context(res)
        try:
            for piece in qa.stream_answer(context, args.query, model):
                yield sse("token", {"text": piece})
        except RuntimeError as e:    # 缺 LLM_API_KEY
            yield sse("error", {"message": f"生成端未就绪：{e}"})
            return
        except Exception as e:
            yield sse("error", {"message": f"生成失败：{str(e)[:200]}"})
            return
        yield sse("done", {})

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


if os.path.isdir(STATIC):
    app.mount("/static", StaticFiles(directory=STATIC), name="static")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    import uvicorn
    print(f"▶ 无人机法律问答服务：http://{args.host}:{args.port}")
    print(f"  生成模型={DEFAULT_MODEL}  检索key={'✓' if os.environ.get('SILICONFLOW_API_KEY') else '✗'}"
          f"  生成key={'✓' if os.environ.get('LLM_API_KEY') else '✗'}")
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
