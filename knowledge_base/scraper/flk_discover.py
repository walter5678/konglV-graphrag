# -*- coding: utf-8 -*-
"""
flk_discover.py
================
用「国家法律法规数据库」(flk.npc.gov.cn) 的搜索接口，做无人机/低空经济相关法规的
【权威发现 + 元数据采集】。

说明（重要）：
- flk 站点为 SPA，正文存于内网 OBS 的 docx，且下载链接与 host 签名绑定，外部无法直接下载。
- 因此本脚本只负责“发现 + 元数据”（法规名、公布/生效日期、时效性、制定机关、法律性质等），
  正文请用 fetch_fulltext.py 从官方 HTML 页面抓取。

接口（2026-07 实测有效）：
- 搜索：POST https://flk.npc.gov.cn/law-search/search/list   (JSON body)
- 详情：GET  https://flk.npc.gov.cn/law-search/search/flfgDetails?bbbs=<id>

输出：raw/flk_catalog.json —— 一份权威的相关法规清单（含元数据），用于指导后续正文采集。
"""
import json
import re
import time
import os
import requests

BASE = "https://flk.npc.gov.cn"
LIST_API = BASE + "/law-search/search/list"
DETAIL_API = BASE + "/law-search/search/flfgDetails"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Referer": "https://flk.npc.gov.cn/",
    "Origin": "https://flk.npc.gov.cn",
}

# 时效性枚举（取自前端 bundle）：1 已废止 2 已修改 3 有效 4 尚未生效
SXX_MAP = {1: "已废止", 2: "已修改", 3: "有效", 4: "尚未生效"}
# searchType: 1 标题检索  2 正文检索
TITLE, CONTENT = 1, 2

# 检索关键词（标题精确命中，覆盖不同表述）
KEYWORDS = [
    "无人驾驶航空器",
    "无人机",
    "低空",
    "通用航空",
    "民用航空器",
]

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "raw")
OUT_FILE = os.path.join(OUT_DIR, "flk_catalog.json")

DELAY = 1.5  # 请求间隔，礼貌抓取


def strip_html(s: str) -> str:
    """去掉标题里的 <em class='highlight'> 高亮标签"""
    return re.sub(r"<[^>]+>", "", s or "").strip()


def search(session, keyword, search_type=TITLE, page=1, size=50):
    """调用搜索接口，返回 (total, rows)"""
    payload = {
        "searchRange": 1,
        "sxrq": [], "gbrq": [], "sxx": [],
        "gbrqYear": [], "flfgCodeId": [], "zdjgCodeId": [],
        "searchType": search_type,
        "searchContent": keyword,
        "page": page,
        "size": size,
    }
    for attempt in range(3):
        try:
            r = session.post(LIST_API, json=payload, headers=HEADERS, timeout=40)
            r.raise_for_status()
            data = r.json()
            if data.get("code") == 200:
                return data.get("total", 0), data.get("rows", []) or []
            return 0, []
        except Exception as e:
            print(f"  [重试 {attempt+1}/3] {keyword} p{page}: {e}")
            time.sleep(2 * (attempt + 1))
    return 0, []


def fetch_detail(session, bbbs):
    """获取详情（附件信息 / OSS 路径，正文无法下载，仅作元数据补充）"""
    try:
        r = session.get(DETAIL_API, params={"bbbs": bbbs}, headers=HEADERS, timeout=40)
        r.raise_for_status()
        d = r.json()
        if d.get("code") == 200:
            data = d.get("data", {}) or {}
            oss = (data.get("ossFile") or {}).get("ossWordPath")
            attaches = [x.get("title") for x in (data.get("xgzl") or [])]
            return {"ossWordPath": oss, "attachments": attaches}
    except Exception as e:
        print(f"  [详情失败] {bbbs}: {e}")
    return {}


def normalize(row):
    """把一条搜索结果规整为统一元数据结构"""
    return {
        "bbbs": row.get("bbbs"),                      # flk 文档唯一 ID（稳定主键）
        "法规名": strip_html(row.get("title")),
        "效力层级": row.get("flxz"),                   # 行政法规 / 地方法规 / 法律 ...
        "制定机关": row.get("zdjgName"),
        "公布日期": row.get("gbrq"),
        "生效日期": row.get("sxrq"),
        "时效性": SXX_MAP.get(row.get("sxx"), row.get("sxx")),
        "flfgCodeId": row.get("flfgCodeId"),
        "zdjgCodeId": row.get("zdjgCodeId"),
        "命中分": row.get("score"),
        "来源": "flk.npc.gov.cn",
    }


def main(with_detail=False, include_content_search=False):
    os.makedirs(OUT_DIR, exist_ok=True)
    session = requests.Session()
    seen = {}   # bbbs -> record（去重）

    search_types = [TITLE] + ([CONTENT] if include_content_search else [])
    for st in search_types:
        st_name = "标题" if st == TITLE else "正文"
        for kw in KEYWORDS:
            page = 1
            total, rows = search(session, kw, st, page=page, size=50)
            print(f"[{st_name}检索] 关键词「{kw}」命中 {total} 条")
            collected = 0
            while rows:
                for row in rows:
                    rec = normalize(row)
                    bbbs = rec["bbbs"]
                    if bbbs and bbbs not in seen:
                        rec["命中方式"] = f"{st_name}:{kw}"
                        seen[bbbs] = rec
                    collected += 1
                if collected >= total:
                    break
                page += 1
                time.sleep(DELAY)
                _, rows = search(session, kw, st, page=page, size=50)
            time.sleep(DELAY)

    catalog = list(seen.values())

    if with_detail:
        print(f"\n拉取 {len(catalog)} 条详情（附件/OSS 元数据）...")
        for rec in catalog:
            info = fetch_detail(session, rec["bbbs"])
            rec.update(info)
            time.sleep(DELAY)

    # 按效力层级 + 生效日期排序，便于人工核对
    catalog.sort(key=lambda x: (str(x.get("效力层级")), str(x.get("生效日期"))), reverse=True)

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 共发现 {len(catalog)} 部相关法规，已写入：{os.path.abspath(OUT_FILE)}")
    # 打印一个概览
    from collections import Counter
    c = Counter(r.get("效力层级") for r in catalog)
    print("按效力层级统计：", dict(c))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--detail", action="store_true", help="额外拉取详情（附件/OSS 路径）")
    ap.add_argument("--content", action="store_true", help="同时做正文检索（召回更多，含提及无人机的法规）")
    args = ap.parse_args()
    main(with_detail=args.detail, include_content_search=args.content)
