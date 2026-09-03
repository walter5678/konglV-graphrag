# -*- coding: utf-8 -*-
"""
ontology.py —— 低空经济无人机法律知识图谱 本体定义（节点/边 schema）。
来自 架构设计_知识图谱RAG.md 第2节。Phase1 结构化产出的「条款单元」即 Article 节点。
"""

# ---- 节点类型 ----
NODE_TYPES = {
    "Regulation": {  # 法规
        "id_field": "law_id",
        "props": ["法规名", "效力层级", "发布机关", "文号", "公布日期", "生效日期", "时效性", "来源URL"],
    },
    "Article": {  # 条款 = 1个结构化单元 = 1个chunk = 向量库主键
        "id_field": "unit_id",
        "props": ["法规名", "law_id", "章", "节", "条号", "条文", "款", "unit_type",
                  "效力层级", "时效性", "生效日期", "来源"],
    },
    "Section": {"id_field": "section_id", "props": ["标题", "序号", "law_id"]},          # 章/节
    "Term": {"id_field": "term", "props": ["术语名", "定义", "别名"]},                    # 术语(LLM抽)
    "DroneCategory": {"id_field": "name", "props": ["名称", "重量阈值", "性能阈值"]},        # 机型分类(枚举)
    "Actor": {"id_field": "name", "props": ["名称"]},                                    # 主体(LLM抽)
    "Activity": {"id_field": "name", "props": ["名称"]},                                 # 活动场景(LLM抽)
    "Sanction": {"id_field": "sanction_id", "props": ["类型", "罚款额度", "描述"]},        # 法律后果(LLM抽)
    "Case": {  # 司法案例(北大法宝 FBMCLI.C.*)——独立子图，元数据可检索
        "id_field": "cli",
        "props": ["标题", "案由", "案号", "审理法院", "文书类型", "审理程序", "案件类型",
                  "相关企业", "审理年份", "审结日期", "时效性", "援引法条", "判决摘要", "来源URL"],
    },
}

# ---- 边类型 ----
EDGE_TYPES = {
    "BELONGS_TO":   ("Article", "Section/Regulation", "属于(结构归属)", "元数据直接建"),
    "REFERENCES":   ("Article", "Article",  "引用(依照第X条)",      "正则+LLM"),
    "BASED_ON":     ("Regulation", "Regulation", "上位法依据",       "效力层级+LLM"),
    "SUPERSEDES":   ("Regulation", "Regulation", "废止/取代(⚠时效)",  "人工+LLM"),
    "DEFINES":      ("Article", "Term",     "定义术语",             "正则+LLM"),
    "APPLIES_TO":   ("Article", "DroneCategory/Activity", "适用于",   "LLM"),
    "OBLIGATES":    ("Article", "Actor",    "义务主体",             "LLM"),
    "PENALIZED_BY": ("Activity/Article", "Sanction", "违反后果",     "LLM"),
    "AMENDS":       ("Article", "Article",  "修正",                 "人工+LLM"),
    "CITES":        ("Case", "Article",     "案例援引法条",          "正则(案例正文《X》第X条→图内Article)"),
}

# 建议先落地：属于/引用/废止取代/定义/适用于 五类，覆盖80%问答。

# ---- 机型分类固定枚举（GB 42590 / 飞行管理暂行条例）----
DRONE_CATEGORIES = ["微型", "轻型", "小型", "中型", "大型"]

# ---- Phase1 条款单元 schema（结构化产出的字段契约）----
UNIT_SCHEMA = [
    "unit_id", "law_id", "法规名", "效力层级", "发布机关", "文号",
    "公布日期", "生效日期", "时效性", "来源", "章", "节", "条号",
    "条文", "款", "unit_type",
]
