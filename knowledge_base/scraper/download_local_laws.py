# -*- coding: utf-8 -*-
"""
download_local_laws.py
======================
下载全国各省市【低空经济相关地方性法规/条例/管理办法】官方全文【原始字节】到本地。
- requests 写 r.content（不解码）；网页存 .html，PDF 存 .pdf
- SSL 容错：DEFAULT@SECLEVEL=1 的 HTTPAdapter；浏览器 UA；timeout=60；重试1次
- 核验：HTTP 200、大小>3KB、HTML 含「第一条」或条例名（UTF-8/GBK 字节）
- 计算 SHA256
最终输出一个 JSON 对象（downloaded / 未获取）到 stdout 与 _result.json
"""
import os
import re
import sys
import json
import time
import hashlib
import requests

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SAVE_DIR = r"D:\schoolwork\competition\低空经济无人机法律智能问答比赛\knowledge_base\law\06_地方性法规"
os.makedirs(SAVE_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/pdf,*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def make_session():
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
                try:
                    ctx.check_hostname = False
                except Exception:
                    pass
                k["ssl_context"] = ctx
                return super().init_poolmanager(*a, **k)

        s.mount("https://", TLSAdapter())
    except Exception:
        pass
    return s


SESSION = make_session()


# 采集目标：每条一部法规。urls 为按优先级排列的官方源（第一个成功即止）。
TARGETS = [
    {
        "法规名": "深圳经济特区低空经济产业促进条例",
        "地区": "深圳市",
        "发布机关": "深圳市人民代表大会常务委员会",
        "文号": "深圳市第七届人民代表大会常务委员会公告",
        "公布日期": "2024-01-03",
        "生效日期": "2024-02-01",
        "时效性": "有效",
        "type": "html",
        "urls": ["https://sqzc.gd.gov.cn/rdzt/wlcy/zcsd/content/post_4366262.html"],
        "备注": "种子；全国首部低空经济专项立法（广东省政策库同文源，深圳人大站证书兼容问题）",
    },
    {
        "法规名": "苏州市低空经济促进条例",
        "地区": "苏州市",
        "发布机关": "苏州市人民代表大会常务委员会",
        "文号": "苏州市人民代表大会常务委员会公告",
        "公布日期": "2025-08-06",
        "生效日期": "2025-10-01",
        "时效性": "有效",
        "type": "html",
        "urls": ["https://www.suzhou.gov.cn/szsrmzf/gbdfxfg/202509/69b369ede5ea4961915f726223faddb5.shtml"],
        "备注": "种子",
    },
    {
        "法规名": "无锡市低空经济发展促进条例",
        "地区": "无锡市",
        "发布机关": "无锡市人民代表大会常务委员会",
        "文号": "无锡市人民代表大会常务委员会公告",
        "公布日期": "2025-08",
        "生效日期": "2025-10-01",
        "时效性": "有效",
        "type": "html",
        "urls": ["https://www.wuxi.gov.cn/doc/2025/08/11/4627089.shtml",
                 "https://www.wxrb.com/doc/2025/08/11/413467.shtml"],
        "备注": "2025-06-27 无锡市人大常委会通过，2025-07-30 江苏省人大常委会批准",
    },
    {
        "法规名": "广州市低空经济发展条例",
        "地区": "广州市",
        "发布机关": "广州市人民代表大会常务委员会",
        "文号": "广州市第十六届人民代表大会常务委员会公告",
        "公布日期": "2025-01-21",
        "生效日期": "2025-02-28",
        "时效性": "有效",
        "type": "html",
        "urls": ["https://www.rd.gz.cn/xwdt/content/post_257581.html",
                 "https://ghzyj.gz.gov.cn/zwgk/newzcfg/ywly/content/post_10120201.html"],
        "备注": "2024-11-29 市人大常委会通过，2025-01-12 广东省人大常委会批准",
    },
    {
        "法规名": "珠海经济特区低空交通建设管理条例",
        "地区": "珠海市",
        "发布机关": "珠海市人民代表大会常务委员会",
        "文号": "珠海市人民代表大会常务委员会〔十届〕第四十五号",
        "公布日期": "2024-11-21",
        "生效日期": "2025-01-01",
        "时效性": "有效",
        "type": "html",
        "urls": ["https://www.hengqin.gov.cn/lab/flfg/zhdffg/content/post_3734944.html"],
        "备注": "经济特区所在市地方性法规；含横琴粤澳深度合作区特别规定",
    },
    {
        "法规名": "济南市低空经济发展促进办法",
        "地区": "济南市",
        "发布机关": "济南市人民政府",
        "文号": "济南市人民政府令",
        "公布日期": "2026",
        "生效日期": "2026",
        "时效性": "有效",
        "type": "html",
        "urls": ["https://www.moj.gov.cn/pub/sfbgw/flfggz/flfggzdfzwgz/202605/t20260513_534843.html"],
        "备注": "地方政府规章（管理办法），司法部地方政府规章库",
    },
    {
        "法规名": "芜湖市低空经济健康发展促进办法",
        "地区": "芜湖市",
        "发布机关": "芜湖市人民政府",
        "文号": "芜湖市人民政府令第75号",
        "公布日期": "2026-01-27",
        "生效日期": "2026-03-01",
        "时效性": "有效",
        "type": "html",
        "urls": ["https://www.wuhu.gov.cn/openness/public/6596211/40511251.html",
                 "https://www.moj.gov.cn/pub/sfbgw/flfggz/flfggzdfzwgz/202604/t20260424_534255.html"],
        "备注": "地方政府规章（管理办法）；安徽省首部低空经济领域地方立法",
    },
    {
        "法规名": "南京市低空飞行服务保障办法(试行)",
        "地区": "南京市",
        "发布机关": "南京市人民政府",
        "文号": "南京市人民政府",
        "公布日期": "2024-11-22",
        "生效日期": "2025-01-01",
        "时效性": "有效",
        "type": "html",
        "urls": ["https://www.nanjing.gov.cn/xxgkn/szgfxwj/202412/t20241203_5024696.html",
                 "https://www.nanjing.gov.cn/zdgk/202412/t20241203_5024658.html"],
        "备注": "行政规范性文件（试行，试行期两年）；低空飞行服务保障办法",
    },
]

ILLEGAL = r'[\\/:*?"<>|\r\n\t]'


def safe_name(s):
    return re.sub(ILLEGAL, "", s).strip()


def unique_path(base_name, ext):
    fn = f"{base_name}{ext}"
    path = os.path.join(SAVE_DIR, fn)
    i = 1
    while os.path.exists(path):
        fn = f"{base_name}_{i}{ext}"
        path = os.path.join(SAVE_DIR, fn)
        i += 1
    return fn, path


def content_ok(content, name, is_pdf):
    """核验正文有效性：>3KB 且含关键标志（排除 JS 空壳）"""
    if len(content) < 3072:
        return False, f"大小仅{len(content)}字节(<3KB)"
    if is_pdf:
        if content[:4] != b"%PDF":
            return False, "非 PDF 魔数"
        return True, ""
    # HTML：检查「第一条」或条例名，分别按 utf-8 / gbk 字节匹配
    needles = ["第一条", name]
    for enc in ("utf-8", "gbk"):
        for nd in needles:
            try:
                if nd.encode(enc) in content:
                    return True, ""
            except Exception:
                pass
    return False, "未检出「第一条」或法规名（疑似JS空壳/跳转页）"


def fetch(url, is_pdf):
    last_err = None
    for attempt in range(2):  # 首次 + 重试1次
        try:
            r = SESSION.get(url, headers=HEADERS, timeout=60, verify=False)
            return r
        except Exception as e:
            last_err = e
            time.sleep(2)
    raise last_err


def process(tgt):
    name = tgt["法规名"]
    region = tgt["地区"]
    is_pdf = tgt.get("type") == "pdf"
    ext = ".pdf" if is_pdf else ".html"
    base_name = safe_name(region + name)

    tried = []
    for url in tgt["urls"]:
        tried.append(url)
        try:
            r = fetch(url, is_pdf)
        except Exception as e:
            print(f"  ✗ 请求失败 {url}: {e}")
            continue
        if r.status_code != 200:
            print(f"  ✗ HTTP {r.status_code} {url}")
            continue
        content = r.content
        ct = r.headers.get("Content-Type", "")
        # 若响应实际为 PDF（附件），改存 pdf
        real_pdf = is_pdf or content[:4] == b"%PDF" or "pdf" in ct.lower()
        use_ext = ".pdf" if real_pdf else ext
        ok, why = content_ok(content, name, real_pdf)
        if not ok:
            print(f"  ✗ 核验失败 {url}: {why}")
            continue
        fn, path = unique_path(base_name, use_ext)
        with open(path, "wb") as f:
            f.write(content)
        sha = hashlib.sha256(content).hexdigest()
        print(f"  ✓ {fn}  {len(content)} bytes  {url}")
        return {
            "法规名": name,
            "类别": "地方性法规",
            "效力层级": "地方政府规章" if "办法" in name else "地方性法规",
            "发布机关": tgt["发布机关"],
            "文号": tgt["文号"],
            "公布日期": tgt["公布日期"],
            "生效日期": tgt["生效日期"],
            "时效性": tgt["时效性"],
            "源URL": url,
            "本地文件名": fn,
            "类型": "pdf" if real_pdf else "html",
            "字节数": len(content),
            "sha256": sha,
            "备注": tgt.get("备注", ""),
        }, None
    # 全部源失败
    return None, {
        "法规名": name,
        "原因": "全部官方源核验失败或请求失败",
        "尝试URL": tried,
    }


def main():
    import urllib3
    urllib3.disable_warnings()
    downloaded = []
    failed = []
    for tgt in TARGETS:
        print(f"抓取：{tgt['地区']}{tgt['法规名']}")
        ok, fail = process(tgt)
        if ok:
            downloaded.append(ok)
        if fail:
            failed.append(fail)
        time.sleep(1.5)

    result = {"downloaded": downloaded, "未获取": failed}
    out = os.path.join(SAVE_DIR, "_download_result.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("\n" + "=" * 60)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n结果已写入 {out}")


if __name__ == "__main__":
    main()
