# -*- coding: utf-8 -*-
"""
scan_missing_body.py
====================
遍历 北大法宝法律法规/*.zip 内所有 PDF（pymupdf 直接读 zip 内存流，不解压），
识别"缺正文"文件并抽取其 附件名 + 原文链接(record url) + 内嵌超链接。

判定思路（基于北大法宝导出PDF的固定版式）：
  正文在最前，随后是"制定机关：/发文字号：/…/【法宝引证码】CLI.x"元数据块，再往后是
  页脚(下载日期/©北大法宝/原文链接)。所以 真正的正文 = 文本[ : 元数据块起点]。
  - body_len：元数据块之前、去掉标题与空白后的字符数
  - has_attachment：正文/尾部出现「附件预览」或「附件：」或「附件N …(.pdf/.doc…)」
  - attachments：抽出的附件文件名
  - record_url：原文链接 https://www.pkulaw.com/lar|chl/{hash}.html
  - links：PDF内嵌全部超链接(去重)

输出 out/missing_body_manifest.json + out/missing_body_report.md
"""
import os, re, sys, io, json, glob, zipfile
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import fitz  # pymupdf

HERE = os.path.dirname(os.path.abspath(__file__))
PKU_DIR = os.path.join(os.path.dirname(HERE), "law", "北大法宝法律法规")
OUT_DIR = os.path.join(HERE, "out")

# 元数据块起点标志（正文到此为止）
META_MARKS = ["制定机关：", "发文字号：", "【法宝引证码】", "公布日期：", "效力位阶："]
# 页脚/联想噪声（正文长度计算时应先切到元数据块之前，这里主要用于兜底）
FOOTER_MARKS = ["©北大法宝", "*注：本文格式", "法宝快讯", "扫描二维码", "下载日期："]

CLI_RE = re.compile(r"【法宝引证码】\s*([A-Za-z0-9.]+)")
URL_RE = re.compile(r"原文链接：\s*(https?://\S+)")
# 附件文件名：附件[数字/空] 名称.(pdf|doc|docx|xls|xlsx|jpg|png|zip|rar)
ATTACH_FILE_RE = re.compile(
    r"附件\s*[0-9一二三四五六七八九十]*[\s:：、.]*([^\n]{0,80}?\.(?:pdf|docx?|xlsx?|jpe?g|png|zip|rar|txt))",
    re.I)
ATTACH_MARK_RE = re.compile(r"附件预览|附件[:：]|见附件|附件\s*[0-9一二三四五六七八九十]")


def fbmcli_from_name(name):
    m = re.search(r"FBMCLI\.([0-9A-Za-z.]+)", name)
    return "FBMCLI." + m.group(1) if m else None


def title_from_name(name):
    b = os.path.basename(name)
    b = re.sub(r"\(FBMCLI[^)]*\)", "", b)
    return re.sub(r"\.pdf$", "", b, flags=re.I).strip()


def body_before_meta(text):
    """返回元数据块之前的正文文本。"""
    idx = len(text)
    for mk in META_MARKS:
        i = text.find(mk)
        if i != -1:
            idx = min(idx, i)
    return text[:idx]


def analyze(text, title):
    body = body_before_meta(text)
    # 去掉正文里重复出现的标题行、全角空格与空白
    core = body
    if title:
        core = core.replace(title, "")
    core_stripped = re.sub(r"\s+", "", core)
    body_len = len(core_stripped)

    has_attach = bool(ATTACH_MARK_RE.search(text))
    attach_files = []
    for m in ATTACH_FILE_RE.finditer(text):
        fn = m.group(1).strip()
        # 去掉可能粘连的前缀标点
        fn = re.sub(r"^[\s:：、.]+", "", fn)
        if fn and fn not in attach_files:
            attach_files.append(fn)

    m = URL_RE.search(text)
    record_url = m.group(1).strip() if m else None
    m = CLI_RE.search(text)
    cli_in_body = m.group(1) if m else None
    return {
        "body_len": body_len,
        "has_attachment": has_attach,
        "attachments": attach_files,
        "record_url": record_url,
        "cli_in_body": cli_in_body,
    }


def collect_links(doc):
    links = []
    for pg in doc:
        for l in pg.get_links():
            u = l.get("uri")
            if u and u not in links:
                links.append(u)
    return links


# 缺正文阈值：元数据块前实质字符数 < 该值视为"正文过短"
SHORT_THRESHOLD = 260


def main():
    zips = sorted(glob.glob(os.path.join(PKU_DIR, "*.zip")))
    print("待扫描 zip:", len(zips))
    rows = []
    stat = {"pdf总数": 0, "抽取失败": 0, "有附件": 0, "正文过短": 0, "缺正文(短且有附件)": 0}
    for z in zips:
        zname = os.path.basename(z)
        try:
            zf = zipfile.ZipFile(z)
        except Exception as e:
            print("打开zip失败", zname, e); continue
        pdfs = [n for n in zf.namelist() if n.lower().endswith(".pdf")]
        for n in pdfs:
            stat["pdf总数"] += 1
            try:
                data = zf.read(n)
                doc = fitz.open(stream=data, filetype="pdf")
                text = "".join(pg.get_text() for pg in doc)
                links = collect_links(doc)
                pages = doc.page_count
                doc.close()
            except Exception as e:
                stat["抽取失败"] += 1
                rows.append({"zip": zname, "file": os.path.basename(n),
                             "error": str(e)[:100]})
                continue
            title = title_from_name(n)
            a = analyze(text, title)
            cli = fbmcli_from_name(n) or a["cli_in_body"]
            short = a["body_len"] < SHORT_THRESHOLD
            if a["has_attachment"]:
                stat["有附件"] += 1
            if short:
                stat["正文过短"] += 1
            if short and a["has_attachment"]:
                stat["缺正文(短且有附件)"] += 1
            rows.append({
                "zip": zname,
                "file": os.path.basename(n),
                "title": title,
                "cli": cli,
                "pages": pages,
                "body_len": a["body_len"],
                "short": short,
                "has_attachment": a["has_attachment"],
                "attachments": a["attachments"],
                "record_url": a["record_url"],
                "links": links,
            })
        zf.close()
        print("  完成", zname)

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "missing_body_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    # 缺正文候选：正文过短 且 有附件；以及 正文过短但无附件(可能纯壳)另列
    missing = [r for r in rows if r.get("short") and r.get("has_attachment")]
    short_noattach = [r for r in rows if r.get("short") and not r.get("has_attachment") and "error" not in r]

    lines = ["# 缺正文扫描报告\n", "## 总计"]
    for k, v in stat.items():
        lines.append("- %s：%d" % (k, v))
    lines.append("\n## 各zip PDF数")
    zc = {}
    for r in rows:
        zc[r["zip"]] = zc.get(r["zip"], 0) + 1
    for k, v in sorted(zc.items()):
        lines.append("- %s：%d" % (k, v))
    lines.append("\n## 缺正文候选（正文过短且有附件）前50")
    for r in missing[:50]:
        lines.append("- [%s] %s ｜ 正文%d字 ｜ 附件%s ｜ %s" % (
            r["cli"], r["title"][:40], r["body_len"],
            r["attachments"] or "(未提取到文件名)", r["record_url"]))
    with open(os.path.join(OUT_DIR, "missing_body_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("\n=== 统计 ===")
    for k, v in stat.items():
        print("%s: %d" % (k, v))
    print("缺正文候选(短+附件):", len(missing), " 短无附件:", len(short_noattach))
    print("输出 ->", OUT_DIR)


if __name__ == "__main__":
    main()
