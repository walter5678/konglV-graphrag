# -*- coding: utf-8 -*-
"""
parse_pkulaw.py
===============
解析北大法宝批量下载的 PDF（法律法规），输出可直接用于 RAG 的分条 chunk。

流程：解压zip -> pdfminer抽文本 -> 正则解析头部元数据块 -> 严格分级过滤
      -> 清洗页眉页脚噪声 -> 按「第X条」切分(复用 fetch_fulltext.parse_articles)
      -> 汇总 chunks + 被丢弃清单 + 统计报告。

用法：
    python parse_pkulaw.py                 # 默认跑 *无人机*.zip 采样包
    python parse_pkulaw.py --all           # 跑目录下全部 zip
    python parse_pkulaw.py a.zip b.zip      # 指定 zip

输出（out/ 下）：
    chunks_pkulaw.json   入库法规 chunk
    dropped.json         被过滤文档清单（引证码/标题/位阶/原因）
    report.md            统计报告
"""
import os, re, sys, json, glob, zipfile, argparse, traceback

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
PKU_DIR = os.path.dirname(HERE) + os.sep + "law" + os.sep + "北大法宝法律法规"  # zip 所在
OUT_DIR = os.path.join(HERE, "out")
WORK_DIR = os.path.join(HERE, "raw_pdf")

# 复用已有的条文切分逻辑
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scraper"))
try:
    from fetch_fulltext import parse_articles
    HAVE_SPLITTER = True
except Exception as e:
    print("⚠️ 未能导入 fetch_fulltext.parse_articles，改用内置简易切分：", e)
    HAVE_SPLITTER = False

# ---- PDF 文本抽取 ----
def pdf_to_text(path):
    from pdfminer.high_level import extract_text
    return extract_text(path)

# ---- 头部元数据解析 ----
FIELD_PATS = {
    "法宝引证码": r"【法宝引证码】\s*([A-Za-z0-9.]+)",
    "发布机关":   r"制定机关：\s*([^\n]+)",
    "文号":       r"发文字号：\s*([^\n]+)",
    "公布日期":   r"公布日期：\s*([0-9./\-]+)",
    "生效日期":   r"施行日期：\s*([0-9./\-]+)",
    "时效性":     r"时效性：\s*([^\n]+)",
    "效力层级":   r"效力位阶：\s*([^\n]+)",
    "法规类别":   r"法规类别：\s*([^\n]+)",
    "来源URL":    r"原文链接：\s*(https?://\S+)",
}
LINK_LABELS = ("机构沿革", "同时废止", "附件预览")

def norm_date(s):
    if not s: return None
    m = re.search(r"(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})", s)
    return "%s-%02d-%02d" % (m.group(1), int(m.group(2)), int(m.group(3))) if m else s.strip()

def clean_val(v):
    v = v.strip()
    for lab in LINK_LABELS:
        v = v.replace(lab, "")
    return re.sub(r"\s{2,}", " ", v).strip()

def title_from_filename(path):
    """北大法宝文件名干净且带 FBMCLI 号，比正文标题更可靠。"""
    b = os.path.basename(path)
    m = re.search(r"FBMCLI\.([0-9.]+)", b)
    cli = "CLI." + m.group(1) if m else None
    name = re.sub(r"\(FBMCLI[^)]*\)", "", b)
    name = re.sub(r"\.pdf$", "", name, flags=re.I).strip()
    return name, cli

def parse_header(text, path=None):
    meta = {}
    for k, pat in FIELD_PATS.items():
        m = re.search(pat, text)
        meta[k] = clean_val(m.group(1)) if m else None
    meta["公布日期"] = norm_date(meta.get("公布日期"))
    meta["生效日期"] = norm_date(meta.get("生效日期"))
    # 标题/引证码优先取自文件名（最可靠）
    fname, fcli = title_from_filename(path) if path else (None, None)
    meta["法规名"] = fname or None
    if not meta.get("法宝引证码"):
        meta["法宝引证码"] = fcli
    return meta

# ---- 正文清洗：去头部块 + 去页眉页脚噪声 + 截掉尾部法宝联想 ----
FOOTER_MARKS = ["引用本篇的法规", "引用本篇", "©北大法宝", "*注：本文格式", "法宝快讯", "本篇引用的法规"]
NOISE_LINE = re.compile(r"^\s*(?:\d+/\d+|下载日期：.*|【法宝引证码】.*|扫描二维码.*|原文链接：.*|附件预览)\s*$")
# 段落起始标志：第X条 / 第X章节 / （数字/中文）/ 一、二、 / 数字、 / 全角缩进
PARA_START = re.compile(r"^\s*(?:第[一二三四五六七八九十百零两0-9]+[条章节款项]|"
                        r"[（(][一二三四五六七八九十0-9]+[）)]|[一二三四五六七八九十]+、|[0-9]+[、.．]|　)")
END_PUNCT = "。；：！？；」）】.:!?"

def dewrap(text):
    """PDF 折行修复：把不是段首、且上一行未以句末标点结束的行并回上一段。"""
    out = []
    for raw in text.splitlines():
        ln = raw.rstrip()
        if not ln.strip():
            continue
        if out and not PARA_START.match(ln) and out[-1] and out[-1][-1] not in END_PUNCT:
            out[-1] += ln.strip()
        else:
            out.append(ln.strip())
    return "\n".join(out)

def clean_body(text, title=None):
    # 头部块结束点：专题分类 行之后；找不到就用 引证码 之后
    anchor = None
    for key in ["专题分类：", "法规类别：", "效力位阶："]:
        m = re.search(key + r"[^\n]*\n", text)
        if m:
            anchor = m.end(); break
    body = text[anchor:] if anchor else text
    # 截掉尾部法宝联想/版权区
    cut = len(body)
    for mk in FOOTER_MARKS:
        i = body.find(mk)
        if i != -1: cut = min(cut, i)
    body = body[:cut]
    # 逐行去噪
    kept = [ln for ln in body.splitlines() if not NOISE_LINE.match(ln)]
    # 相邻重复行去重（北大法宝标题/标号常印两遍）
    dedup = []
    for ln in kept:
        s = ln.strip()
        if s and dedup and s == dedup[-1].strip():
            continue
        dedup.append(ln)
    body = "\n".join(dedup).strip()
    # 从正文里"标题复述处"截断，去掉开头残留的分类词（如"人工智能"）
    if title:
        probe = re.sub(r"《[^》]*》", "", title)[:8]
        i = body.find(probe) if probe else -1
        if 0 < i <= 60:
            body = body[i:]
    return dewrap(body)

# ---- 严格分级过滤 ----
STRONG = {"法律", "行政法规", "部门规章", "地方性法规", "地方政府规章",
          "经济特区法规", "自治条例和单行条例", "宪法"}
SOFT = {"部门规范性文件", "地方规范性文件", "部门工作文件", "行业规定", "团体规定"}
DROP_LEVEL = {"行政许可批复", "行政处罚决定", "行政裁决", "行政复议决定", "立案登记"}
TITLE_KW = ("条例", "办法", "规定", "规则", "细则", "标准", "规范", "准则", "指南", "意见")
# 行政事务性通知的标题特征（虽含"标准/规范"等词，但本身是通知/批复而非规范文本）
NOISE_TITLE_KW = ("下达", "立项", "批准立项", "申办", "征集", "竞赛", "竞速", "选拔",
                   "培训班", "研讨会", "答记者", "参加", "名单", "批复", "通讯赛")
TIAO_RE = re.compile(r"第[一二三四五六七八九十百零两0-9]+条")

def decide_keep(meta, body):
    lvl = (meta.get("效力层级") or "").strip()
    name = meta.get("法规名") or ""
    has_tiao = bool(TIAO_RE.search(body))
    title_struct = any(k in name for k in TITLE_KW)
    if any(k in name for k in NOISE_TITLE_KW):
        return False, "行政事务性通知(非规范文本)"
    if lvl in STRONG:
        return True, "强效力位阶"
    if lvl in DROP_LEVEL:
        return False, "丢弃位阶:" + lvl
    if lvl == "部门工作文件":                      # 工作文件必须真含条文才留
        return (True, "工作文件+含条文") if has_tiao else (False, "部门工作文件(通知/名单)")
    if lvl in SOFT:
        if has_tiao or title_struct:
            return True, "规范性文件+结构化"
        return False, "规范性文件但非结构化(通知/公告)"
    if has_tiao and title_struct:
        return True, "未知位阶但结构化"
    return False, "未知位阶/无条文:" + (lvl or "空")

# ---- 简易切分兜底（无 fetch_fulltext 时用） ----
def simple_split(body):
    parts = re.split(r"(?=第[一二三四五六七八九十百零两0-9]+条)", body)
    arts = []
    for p in parts:
        m = re.match(r"(第[一二三四五六七八九十百零两0-9]+条)", p.strip())
        if m:
            arts.append({"条号": m.group(1), "条文": p.strip(), "章": None, "节": None})
    return arts

def split_articles(body):
    if not TIAO_RE.search(body):
        return [{"条号": None, "条文": body, "章": None, "节": None}]  # 通知/意见类整篇成块
    paras = [ln for ln in body.splitlines() if ln.strip()]
    if HAVE_SPLITTER:
        try:
            arts = parse_articles(paras, mode="条")
            norm = []
            for a in arts:
                norm.append({"条号": a.get("条号") or a.get("article") or a.get("tiao"),
                             "条文": a.get("条文") or a.get("text") or "",
                             "章": a.get("章"), "节": a.get("节")})
            if norm: return norm
        except Exception:
            pass
    return simple_split(body)

# ---- 主流程 ----
def process_pdf(path):
    text = pdf_to_text(path)
    meta = parse_header(text, path)
    body = clean_body(text, meta.get("法规名"))
    keep, reason = decide_keep(meta, body)
    return meta, body, keep, reason

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("zips", nargs="*")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    if args.zips:
        zips = args.zips
    elif args.all:
        zips = sorted(glob.glob(os.path.join(PKU_DIR, "*.zip")))
    else:
        zips = sorted(glob.glob(os.path.join(PKU_DIR, "*无人机*.zip")))  # 默认采样：无人机主题
    print("待处理 zip:", [os.path.basename(z) for z in zips])

    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(WORK_DIR, exist_ok=True)
    chunks, dropped = [], []
    stat = {"pdf总数": 0, "入库文档": 0, "丢弃文档": 0, "生成chunk": 0, "抽取失败": 0}
    level_count = {}

    for z in zips:
        dest = os.path.join(WORK_DIR, os.path.splitext(os.path.basename(z))[0])
        try:
            with zipfile.ZipFile(z) as zf:
                zf.extractall(dest)
        except Exception as e:
            print("解压失败", z, e); continue
        pdfs = glob.glob(os.path.join(dest, "**", "*.pdf"), recursive=True)
        for p in pdfs:
            stat["pdf总数"] += 1
            try:
                meta, body, keep, reason = process_pdf(p)
            except Exception as e:
                stat["抽取失败"] += 1
                dropped.append({"文件": os.path.basename(p), "原因": "抽取异常:" + str(e)[:80]})
                continue
            lvl = meta.get("效力层级") or "?"
            level_count[lvl] = level_count.get(lvl, 0) + 1
            if not keep:
                stat["丢弃文档"] += 1
                dropped.append({"法宝引证码": meta.get("法宝引证码"), "法规名": meta.get("法规名"),
                                "效力层级": lvl, "时效性": meta.get("时效性"), "原因": reason})
                continue
            stat["入库文档"] += 1
            cli = meta.get("法宝引证码") or os.path.basename(p)
            arts = split_articles(body)
            for a in arts:
                tiao = a["条号"] or "全文"
                chunks.append({
                    "法规名": meta.get("法规名"), "效力层级": lvl,
                    "发布机关": meta.get("发布机关"), "文号": meta.get("文号"),
                    "公布日期": meta.get("公布日期"), "生效日期": meta.get("生效日期"),
                    "时效性": meta.get("时效性"), "来源URL": meta.get("来源URL"),
                    "法宝引证码": meta.get("法宝引证码"), "法规类别": meta.get("法规类别"),
                    "章": a["章"], "节": a["节"], "条号": a["条号"],
                    "条文": a["条文"], "chunk_id": "%s::%s" % (cli, tiao),
                })
                stat["生成chunk"] += 1

    with open(os.path.join(OUT_DIR, "chunks_pkulaw.json"), "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT_DIR, "dropped.json"), "w", encoding="utf-8") as f:
        json.dump(dropped, f, ensure_ascii=False, indent=2)

    lines = ["# 北大法宝 PDF 解析报告\n", "## 总计"]
    for k, v in stat.items():
        lines.append("- %s：%d" % (k, v))
    lines.append("\n## 效力位阶分布（全部PDF）")
    for k, v in sorted(level_count.items(), key=lambda x: -x[1]):
        lines.append("- %s：%d" % (k, v))
    lines.append("\n## 入库法规（前40，去重按引证码）")
    seen = set()
    for c in chunks:
        cli = c["法宝引证码"]
        if cli in seen: continue
        seen.add(cli)
        if len(seen) > 40: break
        lines.append("- [%s] %s（%s / %s）" % (cli, c["法规名"], c["效力层级"], c["时效性"]))
    with open(os.path.join(OUT_DIR, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("\n".join(lines[:2] + ["- %s：%d" % (k, v) for k, v in stat.items()]))
    print("\n效力位阶分布：", level_count)
    print("\n输出 -> ", OUT_DIR)

if __name__ == "__main__":
    main()
