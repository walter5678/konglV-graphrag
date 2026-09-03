# -*- coding: utf-8 -*-
"""
build_master_inventory.py —— 合并三源为「全库可chunk源文件总盘点表」。
输入：
  法规清单总表.csv                        law/01~07 精选源 68 行（已人工标注）
  raw/dikongjie_html/inventory_dikongjie.json   低空界 39 行
  pkulaw/out/inventory_pkulaw.json              北大法宝 1649 行
输出（knowledge_base/ 下）：
  全库源文件总盘点表.csv / .md    主表（保留项，跨源去重）
  全库源文件_已排除.csv           附表（重复/剔除/答复批复类）
统一字段：序号,来源,类型,效力层级,标题,发布机关,文号,发布日期,施行日期,
          时效性/现行版本,适用范围,是否已入库,文件路径,来源URL,备注
"""
import os, sys, csv, json, re
sys.stdout.reconfigure(encoding="utf-8")

KB = os.path.dirname(os.path.abspath(__file__))
CSV_LAW = os.path.join(KB, "法规清单总表.csv")
INV_DK = os.path.join(KB, "raw", "dikongjie_html", "inventory_dikongjie.json")
INV_PKU = os.path.join(KB, "pkulaw", "out", "inventory_pkulaw.json")
OUT_MAIN_CSV = os.path.join(KB, "全库源文件总盘点表.csv")
OUT_MAIN_MD = os.path.join(KB, "全库源文件总盘点表.md")
OUT_EXCL_CSV = os.path.join(KB, "全库源文件_已排除.csv")

COLS = ["序号", "来源", "类型", "效力层级", "标题", "发布机关", "文号", "发布日期",
        "施行日期", "时效性/现行版本", "适用范围", "是否已入库", "文件路径", "来源URL", "备注"]


def norm(name):
    return re.sub(r"[（(].*?[)）]", "", name or "").strip().strip("《》 ")


def load_law():
    rows = []
    with open(CSV_LAW, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows.append({
                "来源": "law精选", "类型": "法规", "效力层级": r.get("效力层级"),
                "标题": r.get("标题"), "发布机关": r.get("发布机关"), "文号": r.get("文号"),
                "发布日期": r.get("发布日期"), "施行日期": r.get("施行日期"),
                "时效性/现行版本": r.get("时效性/现行版本"), "适用范围": r.get("适用范围"),
                "是否已入库": r.get("是否已入库"), "文件路径": r.get("文件路径"),
                "来源URL": r.get("来源URL"), "备注": r.get("备注"),
            })
    return rows


def load_dikongjie():
    keep, excl = [], []
    for r in json.load(open(INV_DK, encoding="utf-8")):
        row = {
            "来源": "dikongjie", "类型": r.get("类型"), "效力层级": r.get("效力层级"),
            "标题": r.get("标题"), "发布机关": r.get("地区") or "地方", "文号": "",
            "发布日期": r.get("发布日期"), "施行日期": "",
            "时效性/现行版本": "送审稿/未生效" if r.get("状态") == "待定" else "有效",
            "适用范围": r.get("适用范围"), "是否已入库": "否",
            "文件路径": r.get("文件路径"), "来源URL": r.get("来源URL"),
            "备注": (r.get("备注") or "") + (f"｜{r['条数']}条" if r.get("有无第X条") else "｜无第X条(按段chunk)"),
        }
        if r.get("状态") in ("待chunk", "待定"):
            keep.append(row)
        else:
            row["备注"] = f"[{r.get('状态')}] " + row["备注"]
            excl.append(row)
    return keep, excl


def load_pkulaw():
    keep, excl = [], []
    for r in json.load(open(INV_PKU, encoding="utf-8")):
        row = {
            "来源": "pkulaw", "类型": r.get("类型"), "效力层级": r.get("效力层级"),
            "标题": r.get("标题"), "发布机关": r.get("发布机关"), "文号": r.get("文号"),
            "发布日期": r.get("公布日期"), "施行日期": r.get("施行日期"),
            "时效性/现行版本": r.get("时效性"), "适用范围": None, "是否已入库": "否",
            "文件路径": r.get("文件路径"), "来源URL": r.get("来源URL"),
            "备注": f"引证码{r.get('法宝引证码')}"
                    + ("｜有附件" if r.get("是否有附件") else "")
                    + (f"｜{r.get('原因')}" if r.get("原因") else ""),
        }
        if r.get("keep"):
            keep.append(row)
        else:
            excl.append(row)
    return keep, excl


def main():
    law = load_law()
    dk_keep, dk_excl = load_dikongjie()
    pku_keep, pku_excl = load_pkulaw()

    # 跨源去重：优先级 law > dikongjie > pkulaw
    seen, main_rows, dedup_excl = set(), [], []
    for src in (law, dk_keep, pku_keep):
        for row in src:
            k = norm(row["标题"])
            if k and k in seen:
                row["备注"] = "[跨源重复,已在更高优先源] " + (row["备注"] or "")
                dedup_excl.append(row)
                continue
            if k:
                seen.add(k)
            main_rows.append(row)

    for i, row in enumerate(main_rows, 1):
        row["序号"] = i

    # 写主表 CSV + MD
    with open(OUT_MAIN_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        w.writeheader(); w.writerows(main_rows)

    excl_all = dk_excl + pku_excl + dedup_excl
    with open(OUT_EXCL_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        for i, row in enumerate(excl_all, 1):
            row["序号"] = i
            w.writerow(row)

    # MD 概览
    def by(src): return sum(1 for r in main_rows if r["来源"] == src)
    lines = [
        "# 全库可chunk源文件 总盘点表", "",
        f"> 生成于合并脚本 ｜ 主表 **{len(main_rows)}** 项（跨源去重后）｜ 已排除附表 {len(excl_all)} 项", "",
        "## 来源分布（主表）", "",
        "| 来源 | 项数 | 说明 |", "|---|---|---|",
        f"| law精选 | {by('law精选')} | law/01~07 已人工标注(含适用范围) |",
        f"| dikongjie | {by('dikongjie')} | 低空界地方法规,待chunk |",
        f"| pkulaw | {by('pkulaw')} | 北大法宝筛选保留(法规+案例) |",
        f"| **合计** | **{len(main_rows)}** | |", "",
        "## 类型分布（主表）", "",
    ]
    tdist = {}
    for r in main_rows:
        tdist[r["类型"]] = tdist.get(r["类型"], 0) + 1
    lines.append("| 类型 | 项数 |"); lines.append("|---|---|")
    for k, v in sorted(tdist.items(), key=lambda x: -x[1]):
        lines.append(f"| {k} | {v} |")
    lines += ["", "## 效力层级分布（主表）", "", "| 效力层级 | 项数 |", "|---|---|"]
    ldist = {}
    for r in main_rows:
        ldist[r["效力层级"] or "?"] = ldist.get(r["效力层级"] or "?", 0) + 1
    for k, v in sorted(ldist.items(), key=lambda x: -x[1]):
        lines.append(f"| {k} | {v} |")
    lines += ["", "## 明细", "",
              "完整明细见 `全库源文件总盘点表.csv`（UTF-8-BOM，Excel 可直接开）。",
              "已排除项（重复/答复批复/剔除）见 `全库源文件_已排除.csv`。", "",
              "字段：" + " / ".join(COLS)]
    open(OUT_MAIN_MD, "w", encoding="utf-8").write("\n".join(lines))

    print(f"主表 {len(main_rows)} 项 → {OUT_MAIN_CSV}")
    print(f"  law精选 {by('law精选')}｜dikongjie {by('dikongjie')}｜pkulaw {by('pkulaw')}")
    print(f"已排除 {len(excl_all)} 项 → {OUT_EXCL_CSV}")
    print(f"概览 → {OUT_MAIN_MD}")


if __name__ == "__main__":
    main()
