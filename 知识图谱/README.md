# 低空经济无人机法律 知识图谱构建

配合 `../架构设计_知识图谱RAG.md`（六层架构 + 8节点/9边本体）。
本体定义见 `ontology.py`。构建三阶段：**①结构化/语义分段 → ②抽实体/属性/关系 → ③建图**。

## 目录
```
知识图谱/
├── ontology.py          本体 schema（节点/边/机型枚举/单元字段契约）
├── 1_结构化/
│   ├── structure.py     三源→条款单元(=Article节点=向量库主键)
│   ├── normalize_meta.py 补全/归一 效力层级+时效性(图谱过滤地基)
│   └── out/units_all.json(raw) + units_normalized.json(Phase2消费) + stats.json
├── 2_抽取/              (待做) 正则+LLM 抽 引用/定义/适用/属于...
└── 3_建图/              (待做) 写图库 + 向量库(独立向量DB,硬要求)
```

## Phase1 产出（已完成，2026-08-05）
`1_结构化/out/units_all.json`：**3701 单元 / 132 部法规**
- 来源：existing(现有chunks_all归一) 1680 ｜ dikongjie 905/34部 ｜ pkulaw 1116/99部
- 类型：条 3589 ｜ 语义段 84 ｜ 全文 28 ｜ 含款长条 60
- 案例 499 篇按策略**延后**（结构不同，Phase2前单独一轮）

### 单元字段（= Article 节点 + 向量库 payload）
`unit_id`(=chunk_id,主键) / `law_id`(法规节点ID) / 法规名 / 效力层级 / 发布机关 / 文号 / 公布日期 / 生效日期 / 时效性 / 来源 / 章 / 节 / 条号 / **条文(纯净原文)** / 款(长条内部属性,list) / unit_type

### 切分策略（要点）
- 一条=一单元=一节点；长条不碎裂（款作内部属性）；短定义条不合并。
- 无第X条结构→语义段(200-600字窗口)。
- **条文存纯净原文**（喂Phase2正则抽引用/定义边）；`《法规名》第X条`前缀只在embedding阶段拼。
- 跨源按法规名去重，优先级 existing > dikongjie > pkulaw。
- 清理：跳过征求意见稿/草案（用正式版）；丢"无相关内容"空壳/标题回声/过短噪声。

## ⚠ 已知缺口（Phase2 需处理）
1. ✅**已补齐(2026-08-05, normalize_meta.py)**：效力层级空值0(补全/消歧1030个)、时效性归一为{现行有效3516/已废止160/未生效23/已修改1/部分失效1}、版本注记拆出。
2. ✅**已归一**：效力层级→本体固定枚举(法律/行政法规/部门规章/地方性法规/地方政府规章/部门规范性文件/地方规范性文件/国家标准/行业规定)，带`效力rank`供冲突时高层级优先。
3. law_id 体系混合（法规slug / dikongjie_id / 法宝CLI），但去重后**每部法规1:1对应1个唯一law_id**，直接作 Regulation 节点id即可；`法规名`字段供显示。

## Phase2 输入
`1_结构化/out/units_normalized.json`（3701单元，元数据已补齐归一）。新增字段：`效力rank`(int)、`版本注记`。

## 重跑
```
cd 1_结构化 && python structure.py
```
依赖现有解析器：`knowledge_base/scraper/{fetch_dikongjie,fetch_fulltext}.py`、`knowledge_base/pkulaw/parse_pkulaw.py`。
