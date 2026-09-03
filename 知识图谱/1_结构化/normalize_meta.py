# -*- coding: utf-8 -*-
"""
normalize_meta.py —— Phase1 收尾：补齐并归一元数据，供图谱时效/层级过滤用。
输入 out/units_all.json（structure.py 产出），输出 out/units_normalized.json（Phase2 消费）。

做三件事：
  1. 补全 效力层级（286个pkulaw空值，从 机关/文号/名称 推断）
  2. 效力层级归一到本体固定枚举
  3. 时效性归一为标准状态 {现行有效/已废止/部分失效/已修改/未生效} + 拆出 版本注记
"""
import os, sys, re, json
sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
IN = os.path.join(HERE, "out", "units_all.json")
OUT = os.path.join(HERE, "out", "units_normalized.json")

# 本体固定枚举（含层级rank，用于冲突时高层级优先）
LEVEL_RANK = {
    "宪法": 1, "法律": 2, "行政法规": 3, "部门规章": 4, "地方性法规": 5,
    "地方政府规章": 6, "部门规范性文件": 7, "地方规范性文件": 8,
    "国家标准": 9, "行业规定": 10, "司法案例": 11,
}
LEVEL_MAP = {
    "法律": "法律", "行政法规": "行政法规", "部门规章": "部门规章",
    "地方性法规": "地方性法规", "省级地方性法规": "地方性法规",
    "设区的市地方性法规": "地方性法规", "经济特区法规": "地方性法规",
    "自治条例和单行条例": "地方性法规",
    "地方政府规章": "地方政府规章",
    "部门规范性文件": "部门规范性文件", "地方规范性文件": "地方规范性文件",
    "部门工作文件": "部门规范性文件", "地方工作文件": "地方规范性文件",
    "国家标准(强制)": "国家标准", "国家标准": "国家标准", "标准": "国家标准",
    "行业规定": "行业规定", "团体规定": "行业规定", "司法案例": "司法案例",
}
# 需靠 机关/文号/名称 消歧的粗标签
AMBIGUOUS = {"", "规范性文件", "地方政府规章/规范性文件", "?", None}


def infer_level(name, org, wen):
    n, o, w = name or "", org or "", wen or ""
    if re.search(r"标准|规范", n) and re.search(r"GB|标准", w + n):
        return "国家标准"
    if "政府令" in w or ("人民政府" in o and re.search(r"办法|规定|规章|规程|细则", n)):
        return "地方政府规章"
    if re.search(r"人大|人民代表大会", o) or ("条例" in n and re.search(r"人大", o)):
        return "地方性法规"
    if "条例" in n:
        return "行政法规" if re.search(r"国务院", o) else "地方性法规"
    # 中央部委机关
    if re.search(r"部$|部委|委员会|民航局|中国民用航空局|总局|总署|银行|中国民用航空", o) \
       and not re.search(r"人民政府|人大|地方", o):
        return "部门规章" if re.search(r"规定|办法|规则|规章|细则", n) else "部门规范性文件"
    # 兜底：地方规范性文件
    return "地方规范性文件"


def norm_level(lv, name, org, wen):
    if lv in LEVEL_MAP:
        return LEVEL_MAP[lv]
    if lv in AMBIGUOUS:
        return infer_level(name, org, wen)
    return infer_level(name, org, wen)  # 未知标签也走推断


def norm_timeliness(t):
    """→ (标准状态, 版本注记)"""
    s = t or ""
    note = None
    m = re.search(r"[（(]([^）)]+)[）)]", s)
    if m:
        note = m.group(1)
    if re.search(r"送审|未生效|征求意见", s):
        return "未生效", note
    if "部分" in s and re.search(r"废止|失效", s):
        return "部分失效", note
    if re.search(r"废止|失效", s):
        return "已废止", note
    if "已被修改" in s or "被修改" in s:
        return "已修改", note
    if re.search(r"现行有效|有效", s):
        return "现行有效", note
    return "现行有效", note  # 兜底(已过滤草案,默认现行)


def main():
    units = json.load(open(IN, encoding="utf-8"))
    n_filled, lv_before, lv_after, st_after = 0, {}, {}, {}
    for u in units:
        raw_lv = u.get("效力层级")
        lv_before[raw_lv or "空"] = lv_before.get(raw_lv or "空", 0) + 1
        if raw_lv in AMBIGUOUS:
            n_filled += 1
        u["效力层级"] = norm_level(raw_lv, u.get("法规名"), u.get("发布机关"), u.get("文号"))
        u["效力rank"] = LEVEL_RANK.get(u["效力层级"], 99)
        status, note = norm_timeliness(u.get("时效性"))
        u["时效性"] = status
        u["版本注记"] = note
        lv_after[u["效力层级"]] = lv_after.get(u["效力层级"], 0) + 1
        st_after[status] = st_after.get(status, 0) + 1

    json.dump(units, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"✅ 归一完成 {len(units)} 单元 → {OUT}")
    print(f"   补全/消歧 效力层级 {n_filled} 个")
    print(f"\n效力层级(归一后):")
    for k, v in sorted(lv_after.items(), key=lambda x: LEVEL_RANK.get(x[0], 99)):
        print(f"   {k}: {v}")
    print(f"\n时效性(归一后):")
    for k, v in sorted(st_after.items(), key=lambda x: -x[1]):
        print(f"   {k}: {v}")
    # 校验：仍有空效力层级？
    empt = sum(1 for u in units if not u.get("效力层级"))
    print(f"\n残留空效力层级: {empt}")


if __name__ == "__main__":
    main()
