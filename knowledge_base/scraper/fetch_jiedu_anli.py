# -*- coding: utf-8 -*-
"""
fetch_jiedu_anli.py
===================
下载无人机法规的【官方政策解读/答记者问】与【典型执法/司法案例】官方原始文件。
- requests 写原始字节 (r.content)，不解码；网页 .html，PDF .pdf
- SSL 容错：HTTPAdapter 设 DEFAULT@SECLEVEL=1；浏览器 UA；timeout=60；重试 1 次
- 核验：HTTP 200、大小>3KB、HTML 含正文关键词以排除 JS 空壳
- 计算 SHA256
- 输出 JSON（downloaded / 未获取）
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

OUT_DIR = r"D:\schoolwork\competition\低空经济无人机法律智能问答比赛\knowledge_base\law\07_解读与案例"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/pdf,*/*;q=0.9",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

# 每个目标：标题 / 类别 / 发布机关 / 发布日期 / 关联法规 / url / 类型 / 文件名 / 关键词(校验) / 备注
TARGETS = [
    # ------------------------- 解读 / 答记者问 -------------------------
    {
        "标题": "国家空中交通管理委员会办公室负责人就《无人驾驶航空器飞行管理暂行条例》答记者问",
        "类别": "解读", "发布机关": "司法部/国家空管委办公室", "发布日期": "2023-06-29",
        "关联法规": "无人驾驶航空器飞行管理暂行条例",
        "url": "https://www.moj.gov.cn/pub/sfbgwapp/zwgk/jdhyApp/202306/t20230629_481610.html",
        "类型": "html", "文件名": "空管委办公室负责人就无人驾驶航空器飞行管理暂行条例答记者问.html",
        "kw": ["无人驾驶航空器", "条例"], "备注": "",
    },
    {
        "标题": "《无人驾驶航空器飞行管理暂行条例》政策解读（司法部）",
        "类别": "解读", "发布机关": "司法部", "发布日期": "2023-06-29",
        "关联法规": "无人驾驶航空器飞行管理暂行条例",
        "url": "https://www.moj.gov.cn/pub/sfbgw/zcjd/202306/t20230629_481601.html",
        "类型": "html", "文件名": "司法部_无人驾驶航空器飞行管理暂行条例政策解读.html",
        "kw": ["无人驾驶航空器", "条例"], "备注": "",
    },
    {
        "标题": "专家解读：完善配套措施确保法规落实（《无人驾驶航空器飞行管理暂行条例》）",
        "类别": "解读", "发布机关": "司法部", "发布日期": "2023-06-29",
        "关联法规": "无人驾驶航空器飞行管理暂行条例",
        "url": "https://www.moj.gov.cn/pub/sfbgwapp/zwgk/jdhyApp/202306/t20230629_481607.html",
        "类型": "html", "文件名": "专家解读_完善配套措施确保法规落实.html",
        "kw": ["无人驾驶航空器", "条例"], "备注": "",
    },
    {
        "标题": "《无人驾驶航空器飞行管理暂行条例》解读（司法部信息公开·解读回应）",
        "类别": "解读", "发布机关": "司法部", "发布日期": "2023-06-29",
        "关联法规": "无人驾驶航空器飞行管理暂行条例",
        "url": "https://www.moj.gov.cn/pub/sfbgw/zwxxgk/fdzdgknr/fdzdgknrjdhy/202306/t20230629_481604.html",
        "类型": "html", "文件名": "司法部信息公开_无人驾驶航空器飞行管理暂行条例解读.html",
        "kw": ["无人驾驶航空器", "条例"], "备注": "",
    },
    {
        "标题": "民航局召开视频会议宣贯《民用无人驾驶航空器运行安全管理规则》(CCAR-92部)",
        "类别": "解读", "发布机关": "中国民航局", "发布日期": "2024-03-28",
        "关联法规": "CCAR-92 民用无人驾驶航空器运行安全管理规则",
        "url": "http://www.caacnews.com.cn/special/2024NZT/8024/20191xgbd/202403/t20240328_1376927.html",
        "类型": "html", "文件名": "民航局宣贯CCAR-92运行安全管理规则.html",
        "kw": ["无人驾驶航空器", "CCAR"], "备注": "",
    },
    {
        "标题": "解读 | 《民用无人驾驶航空器经营性飞行活动管理办法（暂行）》",
        "类别": "解读", "发布机关": "中国民航局", "发布日期": "2018-04-09",
        "关联法规": "民用无人驾驶航空器经营性飞行活动管理办法(暂行)",
        "url": "http://www.caac.gov.cn/XXGK/XXGK/ZCJD/201804/t20180409_56264.html",
        "类型": "html", "文件名": "解读_民用无人驾驶航空器经营性飞行活动管理办法.html",
        "kw": ["无人驾驶航空器", "经营"], "备注": "",
    },
    {
        "标题": "解读丨强制性国家标准《民用无人驾驶航空器实名登记和激活要求》(GB 46761-2025)",
        "类别": "解读", "发布机关": "中国民航局", "发布日期": "2026-04-21",
        "关联法规": "GB 46761-2025 民用无人驾驶航空器实名登记和激活要求",
        "url": "http://www.caac.gov.cn/XXGK/XXGK/ZCFBJD/202604/t20260421_230620.html",
        "类型": "html", "文件名": "解读_民用无人驾驶航空器实名登记和激活要求GB46761.html",
        "kw": ["无人驾驶航空器", "实名登记"], "备注": "",
    },
    {
        "标题": "强制性国家标准《民用无人驾驶航空器实名登记和激活要求》重点问题解答",
        "类别": "解读", "发布机关": "中国民航局", "发布日期": "2026-04-21",
        "关联法规": "GB 46761-2025 民用无人驾驶航空器实名登记和激活要求",
        "url": "http://www.caac.gov.cn/XXGK/XXGK/ZCJD/202604/P020260421533372627527.pdf",
        "类型": "pdf", "文件名": "GB46761实名登记和激活要求_重点问题解答.pdf",
        "kw": [], "备注": "",
    },
    {
        "标题": "解读丨强制性国家标准《民用无人驾驶航空器系统运行识别规范》(GB 46750-2025)",
        "类别": "解读", "发布机关": "中国民航局", "发布日期": "2026-01-20",
        "关联法规": "GB 46750-2025 民用无人驾驶航空器系统运行识别规范",
        "url": "https://www.caac.gov.cn/XXGK/XXGK/ZCFBJD/202601/t20260120_229793.html",
        "类型": "html", "文件名": "解读_民用无人驾驶航空器系统运行识别规范GB46750.html",
        "kw": ["无人驾驶航空器", "识别"], "备注": "",
    },
    {
        "标题": "中国民用航空局关于民用无人驾驶航空器监管服务有关事宜的公告",
        "类别": "解读", "发布机关": "中国民航局", "发布日期": "2023-12-31",
        "关联法规": "无人驾驶航空器飞行管理暂行条例",
        "url": "https://www.caac.gov.cn/XXGK/XXGK/TZTG/202312/t20231231_222550.html",
        "类型": "html", "文件名": "民航局关于民用无人驾驶航空器监管服务有关事宜的公告.html",
        "kw": ["无人驾驶航空器", "监管"], "备注": "",
    },
    # ------------------------- 案例 -------------------------
    {
        "标题": "公安部公布依法打击无人机“黑飞”违法犯罪典型案例（8起）",
        "类别": "案例", "发布机关": "公安部", "发布日期": "2026-02-04",
        "关联法规": "无人驾驶航空器飞行管理暂行条例/治安管理处罚法/刑法",
        "url": "https://www.mps.gov.cn/n2254098/n4904352/c10390619/content.html",
        "类型": "html", "文件名": "公安部_无人机黑飞违法犯罪典型案例.html",
        "kw": ["无人机", "黑飞"], "备注": "",
    },
    {
        "标题": "公安部公布依法打击无人机“黑飞”违法犯罪典型案例（新华网发布）",
        "类别": "案例", "发布机关": "新华网/公安部", "发布日期": "2026-02-04",
        "关联法规": "无人驾驶航空器飞行管理暂行条例/治安管理处罚法/刑法",
        "url": "https://www.news.cn/legal/20260204/a7216ea1724e47fe88da2ff845cdc8d3/c.html",
        "类型": "html", "文件名": "新华网_公安部无人机黑飞典型案例.html",
        "kw": ["无人机", "黑飞"], "备注": "公安部案例的权威媒体发布版",
    },
    {
        "标题": "“空中刺客”频现：无人机治理刻不容缓（最高检）",
        "类别": "案例", "发布机关": "最高人民检察院", "发布日期": "2025-12-22",
        "关联法规": "无人驾驶航空器飞行管理暂行条例",
        "url": "https://www.spp.gov.cn/spp/zdgz/202512/t20251222_714201.shtml",
        "类型": "html", "文件名": "最高检_空中刺客频现无人机治理刻不容缓.html",
        "kw": ["无人机"], "备注": "含检察公益诉讼办案情况",
    },
    {
        "标题": "重庆梁平区：检察公益诉讼推动消除无人机“黑飞”隐患（最高检）",
        "类别": "案例", "发布机关": "最高人民检察院", "发布日期": "2026-04-21",
        "关联法规": "无人驾驶航空器飞行管理暂行条例",
        "url": "https://www.spp.gov.cn/spp/dfjcdt/202604/t20260421_726166.shtml",
        "类型": "html", "文件名": "最高检_重庆梁平区检察公益诉讼消除无人机黑飞隐患.html",
        "kw": ["无人机"], "备注": "",
    },
    {
        "标题": "充分发挥职能作用 服务低空经济高质量发展（最高检·无人机黑飞治理）",
        "类别": "案例", "发布机关": "最高人民检察院", "发布日期": "2025-05-26",
        "关联法规": "无人驾驶航空器飞行管理暂行条例",
        "url": "https://www.spp.gov.cn/spp/llyj/202505/t20250526_696560.shtml",
        "类型": "html", "文件名": "最高检_充分发挥职能作用服务低空经济黑飞治理.html",
        "kw": ["无人机", "低空"], "备注": "",
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


def download(url):
    """下载原始字节，重试 1 次。返回 (status_code, content_bytes) 或抛异常。"""
    last_exc = None
    for attempt in range(2):
        try:
            r = SESSION.get(url, headers=HEADERS, timeout=60, verify=False)
            return r.status_code, r.content, r.headers.get("Content-Type", "")
        except Exception as e:
            last_exc = e
            time.sleep(2)
    raise last_exc


def sanitize(name):
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name.strip()


def dedup_path(directory, filename):
    base, ext = os.path.splitext(filename)
    p = os.path.join(directory, filename)
    i = 1
    while os.path.exists(p):
        p = os.path.join(directory, f"{base}_{i}{ext}")
        i += 1
    return p


def html_has_text(content, keywords):
    """解码探测正文；HTML 需含关键词且有足量正文，排除 JS 空壳。"""
    text = None
    for enc in ("utf-8", "gb18030", "gbk"):
        try:
            text = content.decode(enc)
            break
        except Exception:
            continue
    if text is None:
        text = content.decode("utf-8", errors="ignore")
    # 去标签后正文长度
    stripped = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", text)
    stripped = re.sub(r"(?s)<[^>]+>", " ", stripped)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    if len(stripped) < 200:
        return False, len(stripped)
    if keywords:
        if not any(k in text for k in keywords):
            return False, len(stripped)
    return True, len(stripped)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    downloaded, failed = [], []

    import urllib3
    urllib3.disable_warnings()

    for t in TARGETS:
        print(f"下载：{t['标题']}\n      {t['url']}")
        try:
            status, content, ctype = download(t["url"])
        except Exception as e:
            print(f"  ✗ 请求失败：{e}")
            failed.append({"标题": t["标题"], "原因": f"请求异常：{e}", "尝试URL": t["url"]})
            continue

        size = len(content)
        if status != 200:
            print(f"  ✗ HTTP {status}")
            failed.append({"标题": t["标题"], "原因": f"HTTP {status}", "尝试URL": t["url"]})
            continue
        if size < 3 * 1024:
            print(f"  ✗ 太小 {size}B")
            failed.append({"标题": t["标题"], "原因": f"文件过小 {size}B (<3KB)", "尝试URL": t["url"]})
            continue

        # HTML 空壳校验
        if t["类型"] == "html":
            ok, textlen = html_has_text(content, t.get("kw", []))
            if not ok:
                print(f"  ✗ HTML 空壳/缺关键词 (正文{textlen}字)")
                failed.append({"标题": t["标题"],
                               "原因": f"HTML 疑似JS空壳或缺正文关键词(正文{textlen}字)",
                               "尝试URL": t["url"]})
                continue
        else:  # pdf 头校验
            if not content[:5].startswith(b"%PDF"):
                print(f"  ✗ 非PDF内容 (前缀 {content[:8]!r})")
                failed.append({"标题": t["标题"], "原因": f"返回内容非PDF(前缀{content[:8]!r})",
                               "尝试URL": t["url"]})
                continue

        fn = sanitize(t["文件名"])
        path = dedup_path(OUT_DIR, fn)
        with open(path, "wb") as f:
            f.write(content)
        sha = hashlib.sha256(content).hexdigest()
        actual_fn = os.path.basename(path)
        print(f"  ✓ 保存 {actual_fn} ({size}B)")
        downloaded.append({
            "标题": t["标题"], "类别": t["类别"], "发布机关": t["发布机关"],
            "发布日期": t["发布日期"], "关联法规": t["关联法规"], "源URL": t["url"],
            "本地文件名": actual_fn, "类型": t["类型"], "字节数": size,
            "sha256": sha, "备注": t.get("备注", ""),
        })
        time.sleep(1.5)

    result = {"downloaded": downloaded, "未获取": failed}
    out_json = os.path.join(OUT_DIR, "_manifest_解读与案例.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("\n===JSON_RESULT_BEGIN===")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("===JSON_RESULT_END===")


if __name__ == "__main__":
    main()
