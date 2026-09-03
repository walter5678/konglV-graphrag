# -*- coding: utf-8 -*-
"""
build_pkulaw_strict.py —— 北大法宝「严筛」入库：只入正规效力层级的非案例法规。

数据源=out/inventory_pkulaw.json 里 keep=True 且效力层级∈GOOD 的非案例条目(136 条)，
逐 PDF 复用 parse_pkulaw.process_pdf(抽取→清洗→切分)，并叠加二次质量门：
  ①效力层级白名单(GOOD) ②process_pdf 自身的 decide_keep(滤通知/公告/工作文件)
  ③征求意见稿/草案/说明 标题黑名单 ④按法规名与现有 chunks_all 去重。
产出合并进 raw/chunks_all.json(chunk_id 前缀=法宝引证码，可重跑先剔除旧 CLI. 前缀)。
"""
import os, sys, re, json
sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))          # knowledge_base/pkulaw
KB = os.path.dirname(HERE)                                  # knowledge_base
sys.path.insert(0, HERE)
import parse_pkulaw as pk

INVENTORY = os.path.join(HERE, "out", "inventory_pkulaw.json")
CHUNKS_ALL = os.path.join(KB, "raw", "chunks_all.json")

GOOD_LEVELS = {"地方规范性文件", "部门规范性文件", "设区的市地方性法规",
               "省级地方性法规", "部门规章", "行业规定", "经济特区法规"}
# 草案/征求意见稿/说明/答复 不是现行规范文本
BAD_TITLE = re.compile(r"(草案|征求意见稿|送审稿|的说明|答复|批复|公开征求|建议的办理)")
# 产业扶持/招商政策(非法律行为规范)——仅对「无第X条结构的整篇 chunk」剔除，
# 有条文结构的地方管理办法不受影响。
POLICY_TITLE = re.compile(r"(促进.*(发展|经济)|高质量发展|实施意见|指导意见|若干政策|"
                          r"若干意见|若干措施|政策实施细则|奖补|补贴|示范区|产业发展|"
                          r"发展的意见|发展若干|支持.*经济|推动.*经济|加快.*经济)")
FULLTEXT_MIN = 150   # 无条文整篇 chunk 的最低字数(低于此多为发布公告外壳)


def norm_name(n):
    return re.sub(r"[（(].*?[)）]", "", n or "").strip()


def main():
    inv = json.load(open(INVENTORY, encoding="utf-8"))
    strict = [x for x in inv
              if x.get("keep")
              and not str(x.get("法宝引证码", "")).startswith(("FBMCLI.C", "CLI.C"))
              and x.get("效力层级") in GOOD_LEVELS]
    print(f"inventory 严筛候选 {len(strict)} 条")

    allc = json.load(open(CHUNKS_ALL, encoding="utf-8"))
    exist_names = set()
    for c in allc:
        if str(c.get("chunk_id", "")).startswith(("CLI.", "FBMCLI.")):
            continue  # 排除本脚本自身产出，便于重跑
        nm = norm_name(c.get("法规名"))
        if nm:
            exist_names.add(nm)

    new_chunks, added, seen_keys = [], 0, set()
    skip_missing = skip_badtitle = skip_dup = skip_droptext = skip_err = skip_policy = 0

    for x in strict:
        title = x.get("标题") or ""
        if BAD_TITLE.search(title):
            skip_badtitle += 1
            continue
        pdf = os.path.normpath(os.path.join(KB, x["文件路径"]))
        if not os.path.exists(pdf):
            skip_missing += 1
            print(f"  ⚠ 缺PDF: {title[:30]}")
            continue
        try:
            meta, body, keep, reason = pk.process_pdf(pdf)
        except Exception as e:
            skip_err += 1
            print(f"  ⚠ 抽取异常 {title[:24]}: {str(e)[:50]}")
            continue
        # process_pdf 自身的过滤(通知/公告/工作文件/无条文)也要过
        if not keep:
            skip_droptext += 1
            continue
        name = meta.get("法规名") or norm_name(title)
        key = norm_name(name)
        if key in exist_names or key in seen_keys:
            skip_dup += 1
            print(f"  跳过(已有): {name[:30]}")
            continue

        cli = meta.get("法宝引证码") or x.get("法宝引证码") or os.path.basename(pdf)
        # 效力层级以 inventory 为准(process_pdf 有时抽不到)
        lvl = meta.get("效力层级") or x.get("效力层级")
        arts = pk.split_articles(body)
        # 无「第X条」结构 → 整篇成 1 个 chunk。这类里产业扶持政策(非行为规范)
        # 与过短的发布公告外壳价值低，剔除；有条文结构的地方办法不受影响。
        is_fulltext = len(arts) == 1 and (arts[0].get("条号") in (None, "全文"))
        if is_fulltext:
            ft = (arts[0].get("条文") or "").strip()
            if POLICY_TITLE.search(name):
                skip_policy += 1
                continue
            if len(ft.replace("\n", "")) < FULLTEXT_MIN:
                skip_droptext += 1
                continue
        n_before = len(new_chunks)
        for a in arts:
            text = (a["条文"] or "").strip()
            if len(text.replace("\n", "")) < 8:
                continue
            tiao = a["条号"] or "全文"
            new_chunks.append({
                "法规名": name, "效力层级": lvl,
                "发布机关": meta.get("发布机关") or x.get("发布机关"),
                "文号": meta.get("文号") or x.get("文号"),
                "公布日期": meta.get("公布日期") or x.get("公布日期"),
                "生效日期": meta.get("生效日期") or x.get("施行日期"),
                "时效性": meta.get("时效性") or x.get("时效性") or "现行有效",
                "来源URL": meta.get("来源URL") or x.get("来源URL"),
                "章": a["章"], "节": a["节"], "条号": a["条号"],
                "条文": text, "chunk_id": f"{cli}::{tiao}",
            })
        if len(new_chunks) > n_before:
            added += 1
            seen_keys.add(key)
            print(f"  ✓ {name[:30]} | {lvl} | {len(new_chunks)-n_before}条")
        else:
            skip_droptext += 1

    # 合并(先剔除旧的 CLI. 产出以支持重跑)
    allc = [c for c in allc if not str(c.get("chunk_id", "")).startswith(("CLI.", "FBMCLI."))]
    before = len(allc)
    allc.extend(new_chunks)
    json.dump(allc, open(CHUNKS_ALL, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"\n入库法规 {added} 部 / {len(new_chunks)} chunk")
    print(f"跳过：黑名单标题{skip_badtitle}｜产业扶持政策{skip_policy}｜缺PDF{skip_missing}"
          f"｜已有{skip_dup}｜过滤(通知/无条文/过短){skip_droptext}｜异常{skip_err}")
    print(f"chunks_all: {before} → {len(allc)}")


if __name__ == "__main__":
    main()
