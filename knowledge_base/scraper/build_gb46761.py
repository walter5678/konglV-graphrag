# -*- coding: utf-8 -*-
"""
build_gb46761.py —— 解析 GB 46761-2025《民用无人驾驶航空器实名登记和激活要求》
(2026-05-01 强制施行,取代 2017《实名制登记管理规定》),按国标条款号分条,
合并进 raw/chunks_all.json。

关键事实(修正旧记忆):该 PDF 用 **pymupdf** 提取正文质量很好,记忆里"碎片/skip"
是当年用 pdfplumber 的旧结论。唯一难点是条款号被逐行切碎(如 "3." / "1" / 标题、
"5." / "2." / "2." / "1 基本要求"),本脚本用"数字片段组装器 + 层级守卫"重组。

入库范围:第1章范围 / 第2章规范性引用文件 / 第3章术语定义 / 第4章缩略语 /
          第5章实名登记和激活总体流程 / 第6章技术要求 / 第8章标准的实施。
不入库:第7章"测试方法"(样机测试步骤,法律问答价值低,且交叉引用密集易碎)、
        附录A/B/C(接口/加密/JSON 示例表格,pdf页15-21,直接按页范围排除)。
单元粒度:二级条款(如 5.2、6.3),其下三级/四级子条并入;无子条的章(1/2/4/8)整章为一单元。
"""
import sys, io, os, json, re
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
PDF = os.path.join(HERE, "..", "law", "05_标准",
                   "GB 46761-2025 民用无人驾驶航空器实名登记和激活要求.pdf")
OUT_DIR = os.path.join(HERE, "..", "raw")
FULLTEXT = os.path.join(OUT_DIR, "fulltext", "gb46761.json")
CHUNKS_ALL = os.path.join(OUT_DIR, "chunks_all.json")

SLUG = "gb46761"
PAGE_START, PAGE_END = 6, 14          # 0-indexed:正文章节页(第7章测试方法在13-14,附录A起于15)
DROP_CHAPTERS = {7}                    # 第7章测试方法不入库
MIN_LEN = 12                          # 单元去空白后短于此丢弃

META = {
    "法规名": "民用无人驾驶航空器实名登记和激活要求(GB 46761-2025)",
    "效力层级": "国家标准(强制)",
    "发布机关": "国家市场监督管理总局、国家标准化管理委员会",
    "文号": "GB 46761-2025",
    "公布日期": "2025-10-31",
    "生效日期": "2026-05-01",
    "时效性": "有效",
    "来源URL": "https://openstd.samr.gov.cn/bzgk/gb/",
}

DOC_TITLE = "民用无人驾驶航空器实名登记和激活要求"
FOOTER_RE = re.compile(r"^GB\s*46761\s*[-—–]\s*2025$")
FIG_RE = re.compile(r"^图\s*\d+")
NUMFRAG = re.compile(r"^\d+\.$")          # 纯片段 "3."
TERM_TITLE = re.compile(r"^(\d+)\s+(\S.*)$")   # 末片段带标题 "1 告知要求" / 顶章 "3 术语和定义"
TERM_BARE = re.compile(r"^(\d+)$")        # 末片段纯数字 "1"


def page_lines(page):
    """取一页正文行:去页脚(GB行+尾部页码数字)、重复大标题、图注。"""
    raw = [ln.strip() for ln in page.get_text().split("\n")]
    raw = [ln for ln in raw if ln]
    # 去页尾:尾部 GB46761—2025 + 之前的 1~2 个纯数字页码
    while raw and FOOTER_RE.match(raw[-1]):
        raw.pop()
    n = 0
    while raw and n < 2 and TERM_BARE.match(raw[-1]):
        raw.pop(); n += 1
    return [ln for ln in raw
            if ln != DOC_TITLE and not FOOTER_RE.match(ln) and not FIG_RE.match(ln)]


def assemble(lines):
    """把切碎的条款号重组为逻辑行流 [(number|None, text)]。
    number 非空=条款头(text 为同行标题,可空);number=None=正文行。"""
    out, i, n = [], 0, len(lines)
    while i < n:
        ln = lines[i]
        if NUMFRAG.match(ln):                       # 可能是条款号片段
            parts = [ln[:-1]]                        # 去掉尾点
            j = i + 1
            while j < n and NUMFRAG.match(lines[j]):
                parts.append(lines[j][:-1]); j += 1
            title = None
            if j < n:
                mt = TERM_TITLE.match(lines[j])
                mb = TERM_BARE.match(lines[j])
                if mt:
                    parts.append(mt.group(1)); title = mt.group(2).strip()
                elif mb:
                    parts.append(mb.group(1)); title = ""
            if title is not None and 1 <= int(parts[0]) <= 9 and len(parts) <= 4:
                out.append((".".join(parts), title))
                i = j + 1
                continue
            # 组装失败:当作正文,逐行放回
            out.append((None, ln)); i += 1
            continue
        m = TERM_TITLE.match(ln)
        if m and len(m.group(1)) == 1 and 1 <= int(m.group(1)) <= 9:
            out.append((m.group(1), m.group(2).strip()))   # 顶层章一行式 "3 术语和定义"
        else:
            out.append((None, ln))
        i += 1
    return out


def group_key(num):
    p = num.split(".")
    return p[0] if len(p) == 1 else f"{p[0]}.{p[1]}"


def repair_inline_numbers(text):
    """重组正文内被换行切碎的条款号/数值,如 '5.\\n2.\\n2' → '5.2.2'、'92.\\n205条' → '92.205条'、
    '0.\\n25kg' → '0.25kg'。只合并 数字+'.'+换行+数字 的模式,安全。"""
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"(?<=\d)\.\n(?=\d)", ".", text)
    return text


def main():
    import fitz
    doc = fitz.open(PDF)
    lines = []
    for pi in range(PAGE_START, min(PAGE_END + 1, doc.page_count)):
        lines.extend(page_lines(doc[pi]))

    logical = assemble(lines)

    # 逐条款头切叶子;正文并入当前叶子
    leaves, cur = [], None
    for num, text in logical:
        if num is not None:
            cur = {"num": num, "title": text, "body": []}
            leaves.append(cur)
        else:
            if cur is None:                      # 章标题前的零散行(极少),跳过
                continue
            cur["body"].append(text)

    # 按二级前缀分组为单元,跳过第7章
    order, groups, titles = [], {}, {}
    for lf in leaves:
        chap = int(lf["num"].split(".")[0])
        if chap in DROP_CHAPTERS:
            continue
        gk = group_key(lf["num"])
        if gk not in groups:
            groups[gk] = []; order.append(gk)
        groups[gk].append(lf)
        titles[lf["num"]] = lf["title"]

    records, dropped = [], []
    for gk in order:
        chap = int(gk.split(".")[0])
        heading = titles.get(gk, "")
        blocks = []
        for lf in groups[gk]:
            seg = ""
            # 子条(比组键更深)保留其小标题,便于阅读/检索
            if lf["num"] != gk and lf["title"]:
                seg += f"{lf['num']} {lf['title']}\n"
            # 组键自身的标题已由下方 head 承载,不重复输出;仅取其正文
            seg += "\n".join(lf["body"])
            if seg.strip():
                blocks.append(seg.strip())
        body = "\n".join(blocks).strip()
        head = f"{gk} {heading}".strip()
        text = f"{head}\n{body}".strip() if heading else body
        text = repair_inline_numbers(text)
        if len(text.replace("\n", "")) < MIN_LEN:
            dropped.append((gk, text.replace("\n", " ")))
            continue
        rec = dict(META)
        rec.update({"章": f"第{chap}章", "节": heading or None, "条号": gk,
                    "条文": text, "chunk_id": f"{SLUG}::{gk}"})
        records.append(rec)

    os.makedirs(os.path.dirname(FULLTEXT), exist_ok=True)
    json.dump(records, open(FULLTEXT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    allc = json.load(open(CHUNKS_ALL, encoding="utf-8"))
    before = len(allc)
    allc = [c for c in allc if not str(c.get("chunk_id", "")).startswith(SLUG + "::")]
    allc.extend(records)
    json.dump(allc, open(CHUNKS_ALL, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"解析入库 {len(records)} 单元,丢弃(过短) {len(dropped)}")
    print(f"chunks_all: {before} → {len(allc)}")
    print("入库条号:", ", ".join(r["条号"] for r in records))
    if dropped:
        print("丢弃:", "; ".join(f"{g}:{t[:10]}" for g, t in dropped))


if __name__ == "__main__":
    main()
