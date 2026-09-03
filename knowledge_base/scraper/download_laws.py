# -*- coding: utf-8 -*-
"""
download_laws.py
================
下载「无人机/低空经济」相关【国家法律】官方全文原始文件（原始字节，不解码）。
- SSL 容错（DEFAULT@SECLEVEL=1）、浏览器 UA、timeout=60、失败重试1次
- 校验：HTTP 200 且 >3KB；HTML 需字节里含关键词（UTF-8 与 GBK 双编码）
- 计算 SHA256；输出 JSON 报告
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

OUT_DIR = r"D:\schoolwork\competition\低空经济无人机法律智能问答比赛\knowledge_base\law\01_法律"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "application/pdf,*/*;q=0.8"),
    "Accept-Language": "zh-CN,zh;q=0.9",
}

# 目标法律。每条给 主URL + 备选URL；keywords 用于内容校验（除法规名外的正文特征词）。
TARGETS = [
    {
        "法规名": "中华人民共和国民用航空法",
        "发布机关": "全国人民代表大会常务委员会",
        "文号": "主席令（2025年最新修正）",
        "公布日期": "2025-12-27",
        "生效日期": "2026-07-01",
        "时效性": "有效",
        "备注": "2026-07-01施行最新修正版，含无人驾驶航空器专门条款",
        "urls": [
            "https://www.caac.gov.cn/XXGK/XXGK/FLFG/202512/t20251227_229597.html",
        ],
    },
    {
        "法规名": "中华人民共和国治安管理处罚法",
        "发布机关": "全国人民代表大会常务委员会",
        "文号": "主席令第五十四号（2025年修订）",
        "公布日期": "2025-06-27",
        "生效日期": "2026-01-01",
        "时效性": "有效",
        "备注": "2025年修订版，含无人机黑飞、高空抛物等妨害公共安全条款",
        "urls": [
            "http://www.npc.gov.cn/npc/c2/c30834/202506/t20250627_446254.html",
        ],
    },
    {
        "法规名": "中华人民共和国刑法",
        "发布机关": "全国人民代表大会",
        "文号": "主席令（1997修订，历经刑法修正案）",
        "公布日期": "1997-03-14",
        "生效日期": "1997-10-01",
        "时效性": "有效",
        "备注": "现行有效版；候选源择优",
        "urls": [
            "http://gongbao.court.gov.cn/details/f8e30d0689b23f57bfc782d21035c3.html",
            "https://www.spp.gov.cn/spp/fl/201802/t20180206_364975.shtml",
        ],
    },
    {
        "法规名": "中华人民共和国测绘法",
        "发布机关": "全国人民代表大会常务委员会",
        "文号": "主席令第六十七号（2017年修订）",
        "公布日期": "2017-04-27",
        "生效日期": "2017-07-01",
        "时效性": "有效",
        "备注": "2017年第二次修订版，涉无人机航拍测绘资质",
        "urls": [
            "http://www.npc.gov.cn/npc/c30834/201704/b6d1acace3184294b3405bd017ec33c5.shtml",
            "http://www.npc.gov.cn/zgrdw/npc/xinwen/2017-04/27/content_2020927.htm",
        ],
    },
    {
        "法规名": "中华人民共和国数据安全法",
        "发布机关": "全国人民代表大会常务委员会",
        "文号": "主席令第八十四号",
        "公布日期": "2021-06-10",
        "生效日期": "2021-09-01",
        "时效性": "有效",
        "备注": "",
        "urls": [
            "http://www.npc.gov.cn/npc/c2/c30834/202106/t20210610_311888.html",
        ],
    },
    {
        "法规名": "中华人民共和国个人信息保护法",
        "发布机关": "全国人民代表大会常务委员会",
        "文号": "主席令第九十一号",
        "公布日期": "2021-08-20",
        "生效日期": "2021-11-01",
        "时效性": "有效",
        "备注": "涉航拍数据、隐私",
        "urls": [
            "http://www.npc.gov.cn/npc/c2/c30834/202108/t20210820_313088.html",
        ],
    },
    {
        "法规名": "中华人民共和国反恐怖主义法",
        "发布机关": "全国人民代表大会常务委员会",
        "文号": "主席令第三十六号（2018年修正）",
        "公布日期": "2015-12-27",
        "生效日期": "2016-01-01",
        "时效性": "有效",
        "备注": "2018年修正版",
        "urls": [
            "http://www.npc.gov.cn/zgrdw/npc/xinwen/2018-06/12/content_2055871.htm",
        ],
    },
    {
        "法规名": "中华人民共和国突发事件应对法",
        "发布机关": "全国人民代表大会常务委员会",
        "文号": "主席令第二十五号（2024年修订）",
        "公布日期": "2024-06-28",
        "生效日期": "2024-11-01",
        "时效性": "有效",
        "备注": "2024年修订版",
        "urls": [
            "http://www.npc.gov.cn/npc/c2/c30834/202406/t20240628_437888.html",
        ],
    },
    {
        "法规名": "中华人民共和国国家安全法",
        "发布机关": "全国人民代表大会常务委员会",
        "文号": "主席令第二十九号",
        "公布日期": "2015-07-01",
        "生效日期": "2015-07-01",
        "时效性": "有效",
        "备注": "2015年版",
        "urls": [
            "http://www.npc.gov.cn/npc/c10134/201507/5232f27b80084e1e869500b57ecc35d6.shtml",
            "https://npc.gov.cn/zgrdw/npc/xinwen/2015-07/07/content_1941161.htm",
        ],
    },
    {
        "法规名": "中华人民共和国网络安全法",
        "发布机关": "全国人民代表大会常务委员会",
        "文号": "主席令第五十三号",
        "公布日期": "2016-11-07",
        "生效日期": "2017-06-01",
        "时效性": "有效",
        "备注": "涉无人机数据传输/网络运行安全",
        "urls": [
            "http://www.npc.gov.cn/zgrdw/npc/zfjc/zfjcelys/2016-11/07/content_2034939.htm",
            "https://www.cac.gov.cn/2016-11/07/c_1119867116.htm",
        ],
    },
    {
        "法规名": "中华人民共和国民法典-第七编侵权责任",
        "发布机关": "全国人民代表大会",
        "文号": "主席令第四十五号",
        "公布日期": "2020-05-28",
        "生效日期": "2021-01-01",
        "时效性": "有效",
        "备注": "民法典侵权责任编（第七编）官方全文，最高检发布",
        "urls": [
            "https://www.spp.gov.cn/spp/ssmfdyflvdtpgz/202008/t20200831_478419.shtml",
        ],
    },
]


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
                ctx.check_hostname = False
                k["ssl_context"] = ctx
                return super().init_poolmanager(*a, **k)

        s.mount("https://", TLSAdapter())
    except Exception:
        pass
    return s


SESSION = make_session()


def sanitize(name):
    return re.sub(r'[\\/:*?"<>|]', "", name)


def content_ok(content, law_name):
    """字节里是否含关键词（UTF-8 与 GBK 双编码），排除 JS 空壳/反爬页"""
    probes = ["第一条", "第 一 条", law_name, law_name.replace("-", "")]
    # 侵权责任编等分编页可能无"第一条"，补充通用特征
    probes += ["中华人民共和国", "第七编", "侵权责任"]
    for p in probes:
        for enc in ("utf-8", "gbk"):
            try:
                if p.encode(enc) in content:
                    return True
            except Exception:
                pass
    return False


def guess_ext(url, content, ctype):
    ct = (ctype or "").lower()
    u = url.lower()
    if "pdf" in ct or u.endswith(".pdf") or content[:5] == b"%PDF-":
        return "pdf"
    if "msword" in ct or u.endswith(".doc"):
        return "doc"
    if "officedocument" in ct or u.endswith(".docx"):
        return "docx"
    return "html"


def download_one(url):
    last_err = None
    for attempt in range(2):  # 首次 + 重试1次
        try:
            r = SESSION.get(url, headers=HEADERS, timeout=60, verify=False)
            return r, None
        except Exception as e:
            last_err = str(e)
            time.sleep(2)
    return None, last_err


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    import urllib3
    urllib3.disable_warnings()

    downloaded = []
    failed = []
    used_names = set()

    for t in TARGETS:
        law = t["法规名"]
        print(f"\n=== {law} ===")
        ok = False
        errs = []
        for url in t["urls"]:
            r, err = download_one(url)
            if r is None:
                errs.append(f"{url} -> 请求异常:{err}")
                print(f"  x 请求失败 {url}: {err}")
                continue
            code = r.status_code
            content = r.content
            size = len(content)
            print(f"  {url} -> HTTP {code}, {size} bytes")
            if code != 200:
                errs.append(f"{url} -> HTTP {code}")
                continue
            if size <= 3072:
                errs.append(f"{url} -> 过小 {size}B")
                continue
            ctype = r.headers.get("Content-Type", "")
            ext = guess_ext(url, content, ctype)
            if ext == "html" and not content_ok(content, law):
                errs.append(f"{url} -> 内容校验失败(无关键词,疑似空壳)")
                print(f"  x 内容校验失败 {url}")
                continue
            # 通过
            base = sanitize(law)
            fname = f"{base}.{ext}"
            n = 1
            while fname in used_names:
                n += 1
                fname = f"{base}_{n}.{ext}"
            used_names.add(fname)
            path = os.path.join(OUT_DIR, fname)
            with open(path, "wb") as f:
                f.write(content)
            sha = hashlib.sha256(content).hexdigest()
            print(f"  OK -> {fname} ({size}B) sha256={sha[:16]}...")
            downloaded.append({
                "法规名": law,
                "类别": "法律",
                "效力层级": "法律",
                "发布机关": t["发布机关"],
                "文号": t["文号"],
                "公布日期": t["公布日期"],
                "生效日期": t["生效日期"],
                "时效性": t["时效性"],
                "源URL": url,
                "本地文件名": fname,
                "类型": ext,
                "字节数": size,
                "sha256": sha,
                "备注": t.get("备注", ""),
            })
            ok = True
            break
        if not ok:
            failed.append({
                "法规名": law,
                "原因": "; ".join(errs) or "全部候选URL失败",
                "尝试URL": t["urls"],
            })
        time.sleep(1.5)

    report = {"downloaded": downloaded, "未获取": failed}
    print("\n\n=====JSON_REPORT_START=====")
    print(json.dumps(report, ensure_ascii=False, indent=1))
    print("=====JSON_REPORT_END=====")


if __name__ == "__main__":
    main()
