# -*- coding: utf-8 -*-
"""
fetch_dikongjie.py —— 采集 低空界(dikongjie.com) 法律法规库 地方性法规/规范性文件全文，
清洗、按「第X条」解析为 chunk，写入 raw/fulltext/dikongjie.json 并合并进 raw/chunks_all.json。
与现有库按「法规名」去重。
"""
import os, sys, re, json, time
sys.stdout.reconfigure(encoding="utf-8")
import requests
from bs4 import BeautifulSoup
from fetch_fulltext import parse_articles  # 复用「第X条」解析器

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "..", "raw")
FULLTEXT = os.path.join(OUT_DIR, "fulltext", "dikongjie.json")
CHUNKS_ALL = os.path.join(OUT_DIR, "chunks_all.json")
LIST_URL = "https://dikongjie.com/Laws-regulations/?page={}"
DETAIL = "https://dikongjie.com/{}.html"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}

# 清洗：详情页 article 里的导航/统计噪声行
NOISE = re.compile(r"^(法律法规|首页|›|/|正文|\d+\s*评论|\d+\s*赞|本文阅读约.*|\d{4}-\d{2}-\d{2}|[·•]|分享|评论|点赞|收藏)$")
# 免责声明/来源/下载/推荐等站点样板噪声（整行含即删）
DISCLAIM = re.compile(r"(本文内容来自互联网|不代表本站|不对其真实合法性负责|侵犯了您的权益|请及时联系我们|"
                      r"本文观点不代表|仅代表作者本人|请读者仅做参考|内容来自网络|以下为全文|该文观点仅代表|"
                      r"^来源[：:]|^下载[：:]|^分享到|^上一篇|^下一篇|^相关(阅读|推荐|文章))")
# 非法规科普/资讯类标题黑名单
SKIP_TITLE = re.compile(r"(详解|攻略|一览|盘点|科普|须知|哪些国家|大全|排行|榜单)")
QUAN_MIN = 150  # 『全文』类chunk最低字数（低于此视作正文没抓到/纯噪声）

def get(url, tries=3):
    for _ in range(tries):
        try:
            r = requests.get(url, headers=H, timeout=30)
            r.encoding = r.apparent_encoding or r.encoding
            if r.status_code == 200:
                return r.text
        except Exception:
            time.sleep(2)
    return ""

def collect_list():
    """遍历分页收集 (id, 列表标题)。到空页或无新id停。"""
    items, seen = [], set()
    for pg in range(1, 15):
        html = get(LIST_URL.format(pg))
        if not html:
            break
        soup = BeautifulSoup(html, "lxml")
        page_ids = []
        for a in soup.find_all("a", href=True):
            m = re.search(r"dikongjie\.com/(\d{3,6})\.html", a["href"])
            txt = a.get_text(strip=True)
            if m and txt and len(txt) > 8:
                page_ids.append((m.group(1), txt[:80]))
        new = [(i, t) for i, t in page_ids if i not in seen]
        if not new:
            break
        for i, t in new:
            seen.add(i); items.append((i, t))
        time.sleep(1)
    return items

def parse_title(raw):
    """从 '广东珠海：《珠海市低空数据管理办法》' 提取 地区/法规名/效力层级"""
    region = ""
    m = re.match(r"^([^：:]{2,12})[：:]", raw)
    if m and ("：" in raw or ":" in raw):
        region = m.group(1)
    mm = re.search(r"《(.+?)》", raw)
    name = mm.group(1) if mm else re.sub(r"^[^：:]{2,12}[：:]", "", raw).strip("《》 ")
    # 效力层级粗判
    if "条例" in name:
        lvl = "地方性法规"
    elif re.search(r"(办法|规定|规则|细则)", name):
        lvl = "地方政府规章/规范性文件"
    elif re.search(r"(公告|通知|方案|预案|意见|通告|函)", name):
        lvl = "规范性文件"
    else:
        lvl = "地方规范性文件"
    return region, name, lvl

def extract_body(html):
    """取 <article> 正文，清洗噪声与导航头，返回段落列表 + 发布日期"""
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style"]):
        t.decompose()
    art = soup.select_one("article") or soup.body
    date = ""
    md = soup.find(string=re.compile(r"^\d{4}-\d{2}-\d{2}$"))
    if md:
        date = md.strip()
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in art.get_text("\n").split("\n")]
    lines = [ln for ln in lines if ln and not NOISE.match(ln) and not DISCLAIM.search(ln)]
    # 从第一个 第X条/第X章 或明显正文标题起（丢掉列表标题重复行——含《》或地区冒号）
    start = 0
    for i, ln in enumerate(lines):
        if re.match(r"^第[一二三四五六七八九十百]+[章条]", ln):
            start = i; break
    # 若找到第一条，回退到它上面那行正文标题（不含《》）作为标题上下文之后
    body = [ln for ln in lines[start:]]
    # 若从第一条开始，前面标题已丢，OK
    if start == 0:  # 无条结构（通知/公告）：去掉含《》或地区冒号的重复列表标题行
        body = [ln for ln in lines if not (("《" in ln and "》" in ln) or re.match(r"^[^：:]{2,12}[：:]《", ln))]
    return body, date

def main():
    items = collect_list()
    print(f"列表收集到 {len(items)} 条法规")
    if not items:
        print("⚠ 列表为空（网站502/限流？）——中止，不覆盖已有数据。稍后重试。")
        return

    # 现有库法规名（去重）
    allc = json.load(open(CHUNKS_ALL, encoding="utf-8"))
    exist_names = set()
    for c in allc:
        n = c.get("法规名", "")
        if n:
            exist_names.add(re.sub(r"[（(].*?[)）]", "", n).strip())

    records, added, skipped_dup, skipped_empty = [], 0, 0, 0
    seen_slugsafe = set()
    for idx, (did, raw_title) in enumerate(items, 1):
        if SKIP_TITLE.search(raw_title):
            print(f"  [{idx}] 跳过(非法规): {raw_title[:30]}")
            continue
        region, name, lvl = parse_title(raw_title)
        key = re.sub(r"[（(].*?[)）]", "", name).strip()
        if key in exist_names or key in seen_slugsafe:
            skipped_dup += 1
            print(f"  [{idx}] 跳过(已有): {name[:30]}")
            continue
        html = get(DETAIL.format(did))
        if not html:
            continue
        body, date = extract_body(html)
        arts = parse_articles(body, mode="条")
        url = DETAIL.format(did)
        meta = {"法规名": name, "效力层级": lvl, "发布机关": region or "地方",
                "文号": "", "公布日期": date, "生效日期": "", "时效性": "有效", "来源URL": url}
        n_before = len(records)
        if arts:
            for a in arts:
                text = a["条文"].strip()
                if len(text.replace("\n", "")) < 8:
                    continue
                rec = dict(meta); rec.update({"章": a["章"], "节": a["节"], "条号": a["条号"],
                    "条文": text, "chunk_id": f"dikongjie_{did}::{a['条号']}"})
                records.append(rec)
        else:
            # 无条结构：整篇合为一个chunk（须过质量门槛，滤掉只剩免责声明/残缺的）
            full = "\n".join(body).strip()
            if len(full.replace("\n", "")) >= QUAN_MIN:
                rec = dict(meta); rec.update({"章": None, "节": None, "条号": "全文",
                    "条文": full, "chunk_id": f"dikongjie_{did}::全文"})
                records.append(rec)
        got = len(records) - n_before
        if got == 0:
            skipped_empty += 1
        else:
            added += 1; seen_slugsafe.add(key)
        print(f"  [{idx}] {region} {name[:26]} | {lvl} | {got}条")
        time.sleep(1)

    # 写文件 + 合并
    os.makedirs(os.path.dirname(FULLTEXT), exist_ok=True)
    json.dump(records, open(FULLTEXT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    allc = [c for c in allc if not str(c.get("chunk_id","")).startswith("dikongjie_")]
    before = len(allc)
    allc.extend(records)
    json.dump(allc, open(CHUNKS_ALL, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"\n新增法规 {added} 部 / {len(records)} chunk｜跳过(已有){skipped_dup}｜跳过(空){skipped_empty}")
    print(f"chunks_all: {before} → {len(allc)}")

if __name__ == "__main__":
    main()
