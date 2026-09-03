# -*- coding: utf-8 -*-
"""
build_gb42590.py —— 把 GB 42590-2023 扫描件的 OCR 结果(_gb42590_ocr_raw.json)
清洗、按国标条款号解析为分条 chunk，写入 raw/fulltext/gb42590.json 并合并进 raw/chunks_all.json。

入库范围：第1章范围 / 第2章规范性引用文件 / 第3章术语定义(含微轻小型无人机法定定义) /
          第4章安全要求(4.1~4.17 共17项强制要求)。
第5章"试验方法"含大量表格，OCR 后严重碎片化、且属检测操作细节，对法律问答价值低，故不逐条入库。
"""
import sys, io, os, json, re
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "_gb42590_ocr_raw.json")
OUT_DIR = os.path.join(HERE, "..", "raw")
FULLTEXT = os.path.join(OUT_DIR, "fulltext", "gb42590.json")
CHUNKS_ALL = os.path.join(OUT_DIR, "chunks_all.json")

META = {
    "法规名": "民用无人驾驶航空器系统安全要求(GB 42590-2023)",
    "效力层级": "国家标准(强制)",
    "发布机关": "国家市场监督管理总局、国家标准化管理委员会",
    "文号": "GB 42590-2023",
    "公布日期": "2023-05-23",
    "生效日期": "2024-01-01",  # 主要条款提前至2024-01-01实施(配合761号《无人驾驶航空器飞行管理暂行条例》)；全文2024-06-01实施
    "时效性": "有效",
    "来源URL": "https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=0DC41035BA23EF2C5B94E6482492AF1E",
}
SLUG = "gb42590"
MIN_LEN = 12  # 条文去空白后短于此视作纯分组标题，丢弃

# OCR 高频形近错字（该文档语境下安全的替换）
OCR_FIX = [("介人", "介入"), ("奖叶", "桨叶"), ("闪炼", "闪烁"), ("进人", "进入")]

RE_CLAUSE = re.compile(r"^(\d+(?:\.\d+)*)(?=[\s　]|[一-鿿A-Za-z])")


def is_noise(ln):
    s = ln.strip()
    if not s:
        return True
    if re.fullmatch(r"GB\s*42590\s*[-—–]\s*2023", s):     # 页眉
        return True
    if re.fullmatch(r"[0-9]{1,3}", s):                     # 阿拉伯页码
        return True
    if re.fullmatch(r"[ⅠⅡⅢⅣⅤⅥⅦⅧ]+", s):                  # 罗马页码
        return True
    if s == "民用无人驾驶航空器系统安全要求":                 # 重复大标题
        return True
    return False


def fix_ocr(t):
    for a, b in OCR_FIX:
        t = t.replace(a, b)
    return t


def main():
    pages = json.load(open(RAW, encoding="utf-8"))
    lines = []
    for p in pages:
        if p["page"] >= 5:                                 # 跳过封面/目录/前言(1-4页)
            for ln in p["lines"]:
                if not is_noise(ln):
                    lines.append(ln.strip())

    arts = []
    cur_zhang = None
    cur = None
    stopped = False
    last_top = 0  # 已开到的顶层章号；顶层章须严格递增(1→2→3→4→5)，多级号首段须落在已开章内

    def flush():
        if cur and cur["条文"].strip():
            arts.append(cur)

    for ln in lines:
        m = RE_CLAUSE.match(ln)
        if m:
            no = m.group(1)
            body = ln[m.end():].strip()
            first = int(no.split(".")[0])
            if "." not in no:  # 顶层单数字
                is_heading = (body == "" or (len(body) <= 15 and "。" not in body))
                # 须是紧邻的下一章号 + 短标题，才算真章(挡掉表格里的“1 m/s”“5级风力。”)
                if is_heading and first == last_top + 1:
                    if first == 5:           # 到“5 试验方法”——停止，不再逐条入库
                        flush(); cur = None; stopped = True
                        break
                    flush()
                    cur_zhang = ln
                    cur = {"章": ln, "条号": no, "条文": body}
                    last_top = first
                    continue
                if cur is not None:          # 否则视作续行
                    cur["条文"] += "\n" + ln
                continue
            # 多级条款号：首段须落在已开的章内(挡掉表格里的 70.1/76.1/79.1 分贝值)
            if 1 <= first <= last_top:
                flush()
                cur = {"章": cur_zhang, "条号": no, "条文": body}
            else:
                if cur is not None:
                    cur["条文"] += "\n" + ln
        else:
            if cur is not None:
                cur["条文"] += "\n" + ln
    flush()

    # 组装记录 + 过滤纯标题
    records, dropped = [], []
    for a in arts:
        text = fix_ocr(a["条文"].strip())
        no = a["条号"]
        if len(text.replace("\n", "")) < MIN_LEN:
            dropped.append((no, text.replace("\n", " ")))
            continue
        rec = dict(META)
        rec.update({
            "章": a["章"], "节": None, "条号": no, "条文": text,
            "chunk_id": f"{SLUG}::{no}",
        })
        records.append(rec)

    os.makedirs(os.path.dirname(FULLTEXT), exist_ok=True)
    json.dump(records, open(FULLTEXT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    # 合并进 chunks_all：先去掉旧的同法规记录，再追加
    allc = json.load(open(CHUNKS_ALL, encoding="utf-8"))
    before = len(allc)
    allc = [c for c in allc if not str(c.get("chunk_id", "")).startswith(SLUG + "::")]
    allc.extend(records)
    json.dump(allc, open(CHUNKS_ALL, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"到达“5试验方法”停止 = {stopped}")
    print(f"解析入库 {len(records)} 条，丢弃(纯标题) {len(dropped)} 条")
    print(f"chunks_all: {before} → {len(allc)}")
    print("\n入库条号:", ", ".join(r["条号"] for r in records))
    if dropped:
        print("丢弃:", "; ".join(f"{n}:{t[:8]}" for n, t in dropped))


if __name__ == "__main__":
    main()
