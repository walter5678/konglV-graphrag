# -*- coding: utf-8 -*-
"""
fetch_fulltext.py
=================
从官方网站的 HTML 页面抓取法规【正文】，并按「章 / 节 / 条」结构化，
输出可直接用于 RAG 的分条 chunk（每条一条记录，携带完整元数据）。

为什么从 HTML 抓正文：
- flk 的正文走内网 OBS + 签名下载，外部拿不到；
- 而核心法规在政府官网（gov.cn / caac.gov.cn / mee.gov.cn / 地方人大）都有干净 HTML 全文。

用法：
    python fetch_fulltext.py            # 抓取 SOURCES 里配置的全部法规
输出：
    ../raw/fulltext/<slug>.json         # 单部法规的结构化条文
    ../raw/chunks_all.json              # 汇总的全部条文 chunk（供 embedding 用）
"""
import os
import re
import sys
import json
import time
import requests
from bs4 import BeautifulSoup

# Windows 控制台默认 GBK，直接 print 中文/emoji 会崩；统一切到 utf-8
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ---------------------------------------------------------------------------
# 采集源配置：每部法规一条。url 为官方 HTML 全文页。
# 元数据与 RAG chunk 的 metadata schema 对齐（效力层级/发布机关/文号/日期/时效性）。
# ---------------------------------------------------------------------------
SOURCES = [
    {
        "slug": "wrjhkq_feixing_tiaoli",
        "法规名": "无人驾驶航空器飞行管理暂行条例",
        "效力层级": "行政法规",
        "发布机关": "国务院、中央军委",
        "文号": "国务院令、中央军委令第761号",
        "公布日期": "2023-05-31",
        "生效日期": "2024-01-01",
        "时效性": "有效",
        "type": "html",
        "url": "https://www.mee.gov.cn/zcwj/gwywj/202307/t20230706_1035450.shtml",
    },
    {
        "slug": "shenzhen_dikongjingji_tiaoli",
        "法规名": "深圳经济特区低空经济产业促进条例",
        "效力层级": "地方性法规",
        "发布机关": "深圳市人大常委会",
        "文号": "深圳市第七届人大常委会公告",
        "公布日期": "2023-12-29",
        "生效日期": "2024-02-01",
        "时效性": "有效",
        "type": "html",
        # 注：深圳人大 szrd.gov.cn 的 EC 证书与旧版 OpenSSL 不兼容，改用广东省政策库同文源
        "url": "https://sqzc.gd.gov.cn/rdzt/wlcy/zcsd/content/post_4366262.html",
    },
    {
        "slug": "ccar92_yunxing_anquan_guize",
        "法规名": "民用无人驾驶航空器运行安全管理规则(CCAR-92)",
        "效力层级": "部门规章",
        "发布机关": "交通运输部/民航局",
        "文号": "交通运输部令2024年第1号",
        "公布日期": "2023-12-15",
        "生效日期": "2024-01-03",
        "时效性": "有效",
        "type": "pdf",  # caac 页面正文以 PDF 附件形式发布
        "url": "https://www.caac.gov.cn/XXGK/XXGK/MHGZ/202401/P020240103569247124102.pdf",
    },
    {
        "slug": "minyong_hangkong_fa",
        "法规名": "中华人民共和国民用航空法",
        "效力层级": "法律",
        "发布机关": "全国人大常委会",
        "文号": "主席令（2025年最新修正）",
        "公布日期": "2025-12-27",
        "生效日期": "2026-07-01",
        "时效性": "有效",
        "type": "html",
        # 2026-07-01 施行的最新修正版，首次加入无人驾驶航空器专门条款（适航许可、机场管制空域等）
        "url": "https://www.caac.gov.cn/XXGK/XXGK/FLFG/202512/t20251227_229597.html",
    },
    {
        "slug": "jingyingxing_feixing_banfa",
        "法规名": "民用无人驾驶航空器经营性飞行活动管理办法(暂行)",
        "效力层级": "规范性文件",
        "发布机关": "民航局运输司",
        "文号": "MD-TR-2018-01",
        "公布日期": "2018-03-21",
        "生效日期": "2018-06-01",
        "时效性": "有效",
        "type": "pdf",
        "url": "http://www.caac.gov.cn/XXGK/XXGK/GFXWJ/201804/P020180409336678475193.pdf",
    },
    {
        "slug": "gb46761_shimingdengji_jihuo",
        "法规名": "民用无人驾驶航空器实名登记和激活要求(GB 46761-2025)",
        "效力层级": "国家标准(强制)",
        "发布机关": "国家市场监督管理总局、国家标准化管理委员会",
        "文号": "GB 46761-2025",
        "公布日期": "2025-10-31",
        "生效日期": "2026-05-01",
        "时效性": "有效",  # 替代已废止的2017《实名制登记管理规定》
        "type": "pdf",
        "编号方式": "clause",  # 国标用 4/5.1/5.1.1 式条款号，非「第X条」
        # ⚠️ 该 PDF 排版为逐字带空格 + 多栏，pdfplumber 抽出严重碎片，暂排除；
        #    待改用官方 Word 版或人工整理后再入库。
        "skip": True,
        "url": "https://www.caac.gov.cn/XXGK/XXGK/BZGF/BZGF_GJBZ/202601/P020260120370062157303.pdf",
    },
    {
        "slug": "suzhou_dikongjingji_tiaoli",
        "法规名": "苏州市低空经济促进条例",
        "效力层级": "地方性法规",
        "发布机关": "苏州市人大常委会",
        "文号": "苏州市人大常委会公告",
        "公布日期": "2025-07",
        "生效日期": "2025-10-01",
        "时效性": "有效",
        "type": "html",
        "url": "https://www.suzhou.gov.cn/szsrmzf/gbdfxfg/202509/69b369ede5ea4961915f726223faddb5.shtml",
    },
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
}

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "raw")
FULLTEXT_DIR = os.path.join(OUT_DIR, "fulltext")

# 中文数字（用于识别 第X章/节/条）
CN_NUM = r"[一二三四五六七八九十百千零〇两]"
# 条编号：兼容「第一条」(中文) 与「第 92.1 条」(CCAR 数字小数点式)
TIAO_PAT = rf"第\s*(?:{CN_NUM}+|[0-9]+(?:\.[0-9]+)*)\s*条"
# 章/节：兼容「第一章」(中文) 与「A章」(CCAR 字母式)
RE_ZHANG = re.compile(rf"^(?:第{CN_NUM}+章|[A-Z]\s*章)")
RE_JIE   = re.compile(rf"^(?:第{CN_NUM}+节|[A-Z]\s*节)")
RE_TIAO  = re.compile(rf"^{TIAO_PAT}")

# 段内出现的「第X条」（中文数字），用于把挤在同一段落里的多条拆开
CN_TIAO_ANY = re.compile(rf"第({CN_NUM}+)条")
# 国标条款号：4 / 5.1 / 5.1.1（行首，后接空格或中文）
RE_CLAUSE = re.compile(r"^(\d+(?:\.\d+)*)(?=[\s　]|[一-鿿])")

_CN_VALS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
            "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_CN_UNITS = {"十": 10, "百": 100, "千": 1000}


def cn_to_int(s):
    """把中文数字（一 / 二十五 / 一百二十八）转为 int；无法解析返回 None。"""
    if not s:
        return None
    total, num = 0, 0
    for ch in s:
        if ch in _CN_VALS:
            num = _CN_VALS[ch]
        elif ch in _CN_UNITS:
            num = (num or 1) * _CN_UNITS[ch]
            total += num
            num = 0
        else:
            return None
    return total + num


def presplit_paras(paras):
    """把「一段里挤了多条」的段落按第X条切开。
    只在条号构成【递增序列】(n, n+1, n+2…) 时切分，从而避免把正文里的
    交叉引用（如"依照第五条的规定"）误当作新条。"""
    out = []
    for p in paras:
        matches = list(CN_TIAO_ANY.finditer(p))
        if len(matches) <= 1:
            out.append(p)
            continue
        bounds, prev = [0], None
        for m in matches:
            n = cn_to_int(m.group(1))
            if n is None:
                continue
            if prev is None or n == prev + 1:
                if m.start() != 0:
                    bounds.append(m.start())
                prev = n
        bounds = sorted(set(bounds))
        for i, b in enumerate(bounds):
            e = bounds[i + 1] if i + 1 < len(bounds) else len(p)
            seg = p[b:e].strip()
            if seg:
                out.append(seg)
    return out


def make_session():
    """构造带 SSL 容错的会话（部分政府站点 EC 证书与旧 OpenSSL 不兼容）"""
    s = requests.Session()
    try:
        from requests.adapters import HTTPAdapter
        from urllib3.util.ssl_ import create_urllib3_context

        class TLSAdapter(HTTPAdapter):
            def init_poolmanager(self, *a, **k):
                ctx = create_urllib3_context()
                try:
                    ctx.set_ciphers("DEFAULT@SECLEVEL=1")
                except Exception:
                    pass
                k["ssl_context"] = ctx
                return super().init_poolmanager(*a, **k)

        s.mount("https://", TLSAdapter())
    except Exception:
        pass
    return s


SESSION = make_session()


def fetch_html(url):
    r = SESSION.get(url, headers=HEADERS, timeout=40)
    # 编码探测：政府站点可能是 utf-8 或 gbk
    r.encoding = r.apparent_encoding or r.encoding
    return r.text


def fetch_pdf_paragraphs(url):
    """下载 PDF 并逐页抽取文本，返回段落列表（供 parse_articles 使用）"""
    import io
    import pdfplumber

    r = SESSION.get(url, headers=HEADERS, timeout=90)
    r.raise_for_status()
    paras = []
    with pdfplumber.open(io.BytesIO(r.content)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.split("\n"):
                t = re.sub(r"\s+", " ", line).strip()
                # 过滤页眉页脚/纯页码
                if not t or re.fullmatch(r"[-—\s]*\d+[-—\s]*", t):
                    continue
                # 过滤目录点导行（如「5.1 实名登记流程 ……… 2」）——点导+页码，非正文
                if re.search(r"[…\.]{4,}\s*\d+\s*$", t) or "…" in t:
                    continue
                paras.append(t)
    return paras


def extract_paragraphs(html):
    """从 HTML 抽取正文段落列表（尽量鲁棒，兼容不同政府站点模板）"""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    # 常见正文容器选择器（按命中优先级）
    selectors = [
        "#UCAP-CONTENT", ".TRS_Editor", ".TRS_UEDITOR", ".pages_content",
        ".content", "#Zoom", ".article-content", ".view", "#zoom",
    ]
    container = None
    for sel in selectors:
        node = soup.select_one(sel)
        if node and len(node.get_text(strip=True)) > 200:
            container = node
            break
    if container is None:
        container = soup.body or soup

    # 逐段取文本；用 <p> 优先，否则按换行拆
    paras = []
    p_tags = container.find_all("p")
    if p_tags and sum(len(p.get_text(strip=True)) for p in p_tags) > 200:
        for p in p_tags:
            t = p.get_text(separator=" ", strip=True)
            t = re.sub(r"\s+", " ", t).strip()
            if t:
                paras.append(t)
    else:
        for line in container.get_text("\n").split("\n"):
            t = re.sub(r"\s+", " ", line).strip()
            if t:
                paras.append(t)
    return paras


def parse_articles(paras, mode="条"):
    """把段落列表解析为分条结构，维护 章/节 上下文。
    mode="条"    ：按「第X条」解析（法律/行政法规/规章/地方性法规）
    mode="clause"：按「4 / 5.1 / 5.1.1」式条款号解析（国家标准）"""
    if mode == "clause":
        return _parse_clauses(paras)

    paras = presplit_paras(paras)  # 先把挤在一段的多条拆开
    articles = []
    cur_zhang = None
    cur_jie = None
    cur = None  # 当前正在累积的“条”

    def flush():
        if cur and cur["条文"].strip():
            articles.append(cur)

    for p in paras:
        if RE_ZHANG.match(p):
            flush(); cur = None
            cur_zhang = p
            cur_jie = None
            continue
        if RE_JIE.match(p):
            flush(); cur = None
            cur_jie = p
            continue
        if RE_TIAO.match(p):
            flush()
            # 拆出“第X条”标号与其后的正文（兼容中文/数字两种编号）
            m = re.match(rf"^({TIAO_PAT})\s*(.*)$", p)
            tiao_no = re.sub(r"\s+", "", m.group(1)) if m else p[:6]
            body = m.group(2) if m else p
            cur = {"章": cur_zhang, "节": cur_jie, "条号": tiao_no, "条文": body}
        else:
            # 续行：附到当前条（款/项）
            if cur is not None:
                cur["条文"] += "\n" + p
    flush()
    return articles


def _parse_clauses(paras):
    """按国标条款号（4 / 5.1 / 5.1.1）解析。顶层整数号（4/5/6…）视作『章』上下文。"""
    articles = []
    cur_zhang = None
    cur = None

    def flush():
        if cur and cur["条文"].strip():
            articles.append(cur)

    for p in paras:
        m = RE_CLAUSE.match(p)
        if m:
            no = m.group(1)
            body = p[m.end():].strip()
            if "." not in no:  # 顶层条款，如「4 术语和定义」——作为章标题
                flush(); cur = None
                cur_zhang = p
                continue
            flush()
            cur = {"章": cur_zhang, "节": None, "条号": no, "条文": body}
        else:
            if cur is not None:
                cur["条文"] += "\n" + p
    flush()
    return articles


def process(src):
    print(f"抓取：{src['法规名']}  [{src.get('type','html')}]")
    if src.get("type") == "pdf":
        paras = fetch_pdf_paragraphs(src["url"])
    else:
        html = fetch_html(src["url"])
        paras = extract_paragraphs(html)
    articles = parse_articles(paras, mode=src.get("编号方式", "条"))

    records = []
    for art in articles:
        rec = {
            "法规名": src["法规名"],
            "效力层级": src["效力层级"],
            "发布机关": src["发布机关"],
            "文号": src["文号"],
            "公布日期": src["公布日期"],
            "生效日期": src["生效日期"],
            "时效性": src["时效性"],
            "来源URL": src["url"],
            "章": art["章"],
            "节": art["节"],
            "条号": art["条号"],
            "条文": art["条文"].strip(),
            "chunk_id": f"{src['slug']}::{art['条号']}",
        }
        records.append(rec)

    os.makedirs(FULLTEXT_DIR, exist_ok=True)
    out = os.path.join(FULLTEXT_DIR, src["slug"] + ".json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"  解析出 {len(records)} 条 -> {os.path.abspath(out)}")
    return records


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    all_chunks = []
    for src in SOURCES:
        if src.get("skip"):
            print(f"跳过（待人工整理）：{src['法规名']}")
            continue
        try:
            all_chunks.extend(process(src))
        except Exception as e:
            print(f"  ✗ 失败：{src['法规名']} - {e}")
        time.sleep(2)

    combined = os.path.join(OUT_DIR, "chunks_all.json")
    with open(combined, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 汇总 {len(all_chunks)} 条 chunk -> {os.path.abspath(combined)}")


if __name__ == "__main__":
    main()
