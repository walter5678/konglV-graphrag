# 7_评测 —— GraphRAG 问答系统评测

评测分两层，对应系统"检索质量决定答案质量"的事实：

- **检索层**（全自动、零成本，`--mode sparse` 免 API key）：命中率/召回/排序
- **生成层**（LLM-as-judge + 抽样人工）：忠实度/正确性/时效性/引用

## gold.jsonl —— 标注评测集（一行一题）

字段 schema：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | str | 题号 Q01… |
| `question` | str | 用户问题（口语化，贴近真实提问） |
| `category` | str | 考点分类：机型分类/实名登记/空域管制/飞行申请/操控资质/适航/罚则/行为规范/安全要求/特殊活动 |
| `difficulty` | str | `single`=单条可答 / `multi`=需多条综合 / `graph`=需图扩展关联条款 |
| `gold_parent_ids` | list[str] | **应被检索命中**的权威条文 id（= 向量库 parent_id = 图节点 id）。检索层用它算 Hit@k/Recall/MRR/nDCG |
| `avoid_ids` | list[str] | **不该排在前排**的已废止/易混淆条文。时效错误率用它 |
| `gold_laws` | list[str] | 应引用的法规名（去重）。生成层评引用正确性用 |
| `key_points` | list[str] | 标准答案要点。生成层评正确性（覆盖率）用 |
| `trap` | str | （可选）陷阱说明：时效性/机型混淆等 |
| `note` | str | 标注依据（人工复核用） |

### 标注规则

1. `gold_parent_ids` 只列**真实存在**于 `5_向量库/out/parents.json` 的 id，且是回答该题**最核心**的 1~3 条（多条综合题可更多）。不追求穷举，追求"命中这些就算检索成功"。
2. `avoid_ids` 用于时效陷阱题：如实名登记题里 2017 已废止的 `CLI.4.294943::全文` 不得排在现行版之前。
3. `key_points` 基于条文原文人工提炼，是生成答案正确性的评分锚点。
4. id 格式：`<law_id>::<条号>`，如 `wrjhkq_feixing_tiaoli::第十条`、`gb46761::5.2`、`CLI.10.9785475::第四条`。

## 脚本（待建）

- `eval_retrieval.py` —— 遍历 gold × 检索配置（dense/sparse/hybrid/+rerank/+expand），输出 Hit@k/Recall@k/MRR/nDCG@k + **消融对比表**
- `eval_generation.py` —— 跑 qa 生成 → LLM-judge 打分（忠实度/正确性/时效/引用）
- `report.py` —— 汇总成 markdown（答辩/演示直接用）
