# 低空经济无人机法律智能问答系统

> 基于 **GraphRAG（知识图谱增强检索 + 大模型生成）** 的中国无人机法律法规问答系统。
> 覆盖 **107 部法规 + 531 个案例**，答案带**法条引用**与**时效性标注**，附 GPT 风格 Web 界面。

比赛命题「命题3-低空经济无人机法律法规智能问答系统」的完整实现。设计文档见
[`架构设计_知识图谱RAG.md`](架构设计_知识图谱RAG.md)。

---

## 系统能做什么

- **问答带引用**：每个结论标注《法规名》第X条，不臆造法条。
- **时效性感知**：自动区分现行有效 / 已废止 / 已修改 / 未生效，废止旧法不作现行依据（如 2017《实名制登记规定》已被 GB 46761-2025 取代）。
- **知识图谱多跳**：向量召回的条文之外，沿「引用 / 同机型 / 同义务主体」图边扩展出结构相关的关联条款，带溯源。
- **机型阈值区分**：微型 / 轻型 / 小型 / 中型 / 大型的重量·性能阈值与对应义务差异。
- **案例维度**：531 个低空/无人机企业涉诉案例可检索（独立子图）。

---

## 检索链（GraphRAG 六阶段）

```
107 法规 + 531 案例
  ①结构化  → 3586 单元(条文/元数据归一)
  ②LLM抽取 → 术语/机型/主体/场景/罚则 + 语义边
  ③建图    → Neo4j 图谱 6650 节点 / 11557 边
  ④向量库  → 父子分块 → BGE-M3 嵌入 → Chroma (4837 child)
  ⑤检索    → 查询路由 → hybrid(BGE-M3稠密 + BM25稀疏) RRF融合(alpha≈0.9)
              → 时效过滤 → bge-reranker 精排 → Neo4j 图多跳扩展(稀有度降权)
  ⑥生成    → LLM(默认智谱GLM-4-Flash) 依据检索条文出带引用答案
```

三种模型分工：**BGE-M3**（召回嵌入）/ **bge-reranker-v2-m3**（精排）/ **GLM-4-Flash**（生成，可换任意 OpenAI 兼容模型）。

---

## 快速开始

### 0. 依赖

- **Python 3.8**，已装：`fastapi uvicorn openai chromadb jieba rank_bm25 neo4j`
  （缺失时 `pip install fastapi uvicorn openai "chromadb==0.4.24" jieba rank_bm25 neo4j "posthog==2.5.0"`）
- **Neo4j 社区版**（本机在 `D:\Neo4j\neo4j-community\neo4j-community-2026.06.0`）
- **两个 API Key（都可零成本获取）**：
  - **生成端**：[智谱开放平台](https://open.bigmodel.cn) 的 `GLM-4-Flash` —— **永久免费、不限 token**，国内直连。
  - **检索端**：[SiliconFlow](https://siliconflow.cn) 的 `BGE-M3` 嵌入 —— 免费模型，新用户注册送额度；嵌入消耗极低。
    （若只想临时零成本演示，可用 `--mode sparse` 纯关键词检索，完全不需要 SiliconFlow key。）

### 1. 启动 Neo4j（图谱库）

```powershell
D:\Neo4j\neo4j-community\neo4j-community-2026.06.0\bin\neo4j.bat console
# 保持此窗口开着；默认端口 7687，用户 neo4j / 密码 12345678
```

首次或图谱重建后需导入数据（数据已就绪，仅换机/清库后需要）：

```powershell
$cs="D:\Neo4j\neo4j-community\neo4j-community-2026.06.0\bin\cypher-shell.bat"
& $cs -a bolt://localhost:7687 -u neo4j -p 12345678 "MATCH (n) DETACH DELETE n;"
& $cs -a bolt://localhost:7687 -u neo4j -p 12345678 -f "知识图谱\3_建图\out\neo4j_import.cypher"
# ⚠ 必须用 -f 读文件，不能用 Get-Content|管道（PowerShell 管道会破坏 UTF-8 BOM 致语法错）
```

### 2. 配置密钥（不写盘，只设环境变量）

```powershell
# 检索端：SiliconFlow（BGE-M3 嵌入 / rerank）
$env:SILICONFLOW_API_KEY = "sk-硅基流动的key"
# 生成端：智谱 GLM-4-Flash（永久免费，默认值，无需再设 BASE_URL/MODEL）
$env:LLM_API_KEY         = "智谱开放平台的key"
$env:NEO4J_PASSWORD      = "12345678"

# —— 若想改用别的 OpenAI 兼容生成模型，额外设这两个即可（默认已是智谱 GLM）——
# $env:LLM_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"   # 智谱(默认)
# $env:LLM_MODEL    = "glm-4-flash"                            # 智谱(默认)
# 例：SiliconFlow 上的 DeepSeek-V3 →
#   $env:LLM_BASE_URL="https://api.siliconflow.cn/v1"; $env:LLM_MODEL="deepseek-ai/DeepSeek-V3"
```

> **零成本演示**：生成端默认智谱 GLM-4-Flash 永久免费；检索端若暂无 SiliconFlow 额度，
> 界面里把「模式」切到 **sparse**（纯关键词，不调嵌入 API），即可全免费跑通。

### 3. 启动 Web 服务

```powershell
cd 知识图谱\6_问答
python server.py                    # → http://127.0.0.1:8000
# 或 python server.py --host 0.0.0.0 --port 8080   （对外/换端口）
```

浏览器打开 **http://127.0.0.1:8000**，即得 GPT 风格问答界面。

---

## 命令行用法（无界面）

```powershell
cd 知识图谱\6_问答

# 完整链问答（推荐）
python qa.py --query "无人机在管制空域飞行需要什么条件？未经批准飞行怎么处罚？" `
  --rerank --expand --only-current --neo4j-pwd 12345678
# 默认生成模型=智谱 glm-4-flash；换模型加 --model，如 --model deepseek-ai/DeepSeek-V3

# 只看检索上下文，不调生成模型（省 key，验证检索）
python qa.py --query "微型无人机的重量标准" --show-context

# 纯检索（无生成），可对比 hybrid/dense/sparse 三模式
cd ..\5_向量库
python search.py --query "适航审定" --mode hybrid --rerank --expand --only-current --neo4j-pwd 12345678
```

**免 SiliconFlow key 的降级链**：`--mode sparse`（纯 BM25 关键词检索 + 图扩展，不需嵌入 API），仅生成端仍需 LLM key。

---

## 演示问答示例

| 问题 | 展示能力 |
|------|----------|
| 无人机在管制空域飞行需要什么条件？未经批准飞行怎么处罚？ | 条件+罚则多跳、区分管制/适飞空域 |
| 微型、轻型、小型无人机怎么划分？重量标准分别是多少？ | 机型阈值、法定分类 |
| 无人机实名登记有哪些要求？不登记会怎样？ | 义务+后果、时效性 |
| 无人机适航审定适用于哪些机型？ | 机型→条款遍历、图扩展 |

---

## 界面说明

- **模式**：hybrid（向量+关键词，默认）/ dense（纯向量）/ sparse（纯关键词，免检索 key）
- **精排 rerank**：cross-encoder 二阶段精排，默认开
- **图谱扩展**：Neo4j 多跳关联条款，默认开
- **仅现行有效**：过滤已废止/未生效条文，默认开
- 答案下方 **📎 引用来源** 可展开，分「主要条文」与「关联条款（知识图谱扩展）」，每条可点开看全文、带时效标签与溯源。

---

## 异地部署三依赖（换机演示必带）

1. **联网 + SiliconFlow key** —— 生成/嵌入/精排都走云 API。
2. **Chroma 向量库** —— 物理位置在 `C:\Users\<用户>\drone_law_chroma`（因项目路径含中文，
   hnswlib 无法写非 ASCII 路径，故落在用户目录）。换机需**整目录拷贝**，并设
   `$env:DRONE_CHROMA_DIR = "拷贝后的路径"`。
3. **Neo4j** —— 换机需装 Neo4j 并重导 `知识图谱\3_建图\out\neo4j_import.cypher`（见上），
   或让演示机远程连回本机的 7687。

---

## 目录结构

```
知识图谱/
  1_结构化/   structure.py normalize_meta.py         → units_normalized.json
  2_抽取/     vocab.py(受控词表/归一) build_*.py       → nodes_llm/edges_llm.json
  3_建图/     build_graph.py                          → graph_export.json + neo4j_import.cypher
  4_案例/     build_cases.py                          → 531 Case 节点
  5_向量库/   build_chunks/vectordb/bm25.py
              search.py(检索链: retrieve/expand)
              graph_expand.py(图多跳+稀有度降权)
  6_问答/     qa.py(CLI端到端问答)
              server.py(FastAPI + SSE 流式后端)
              static/index.html(GPT 风格前端)
knowledge_base/   原始语料与采集脚本
架构设计_知识图谱RAG.md
```

---

## 说明与局限

- **答案质量 = 检索质量**：系统严格「只依据检索到的条文作答」，不臆造。若某主题的权威法规
  未入库（如 GB 46761-2025 实名登记国标因原 PDF 为碎片扫描件暂未整理入库），答案可能退而
  引用地方法规，需注意补库。
- 答案由 AI 生成，**仅供参考，不构成法律意见**。
- API key 请通过环境变量传入，切勿写入代码或提交到版本库；若曾在聊天/日志中明文出现，请及时轮换。
