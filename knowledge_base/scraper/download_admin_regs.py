# -*- coding: utf-8 -*-
import os, re, json, hashlib, time
import requests
from requests.adapters import HTTPAdapter
try:
    from urllib3.util.ssl_ import create_urllib3_context
except Exception:
    from urllib3.util.ssl_ import create_urllib3_context

SAVE_DIR = r"D:\schoolwork\competition\低空经济无人机法律智能问答比赛\knowledge_base\law\02_行政法规"
os.makedirs(SAVE_DIR, exist_ok=True)

class SSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *a, **k):
        ctx = create_urllib3_context(ciphers='DEFAULT@SECLEVEL=1')
        try:
            ctx.check_hostname = False
        except Exception:
            pass
        import ssl as _ssl
        ctx.verify_mode = _ssl.CERT_NONE
        k['ssl_context'] = ctx
        return super().init_poolmanager(*a, **k)
    def proxy_manager_for(self, *a, **k):
        ctx = create_urllib3_context(ciphers='DEFAULT@SECLEVEL=1')
        import ssl as _ssl
        ctx.check_hostname = False
        ctx.verify_mode = _ssl.CERT_NONE
        k['ssl_context'] = ctx
        return super().proxy_manager_for(*a, **k)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def make_session():
    s = requests.Session()
    s.mount("https://", SSLAdapter())
    s.mount("http://", SSLAdapter())
    s.headers.update(HEADERS)
    return s

def sanitize(name):
    return re.sub(r'[\\/:*?"<>|]', '', name)

def unique_path(base, ext):
    fn = sanitize(base) + ext
    p = os.path.join(SAVE_DIR, fn)
    i = 1
    while os.path.exists(p):
        fn = sanitize(base) + f"_{i}" + ext
        p = os.path.join(SAVE_DIR, fn)
        i += 1
    return fn, p

def ext_from(url, content, ctype):
    ctype = (ctype or "").lower()
    u = url.lower()
    if u.endswith(".pdf") or "application/pdf" in ctype or content[:4] == b"%PDF":
        return ".pdf"
    if u.endswith(".docx") or "openxmlformats" in ctype:
        return ".docx"
    if u.endswith(".doc") or "msword" in ctype:
        return ".doc"
    return ".html"

def check_content(content, ext, law_name):
    if ext == ".pdf":
        return content[:4] == b"%PDF", "PDF magic"
    # try decode
    texts = []
    for enc in ("utf-8", "gbk", "gb18030"):
        try:
            texts.append(content.decode(enc, errors="ignore"))
        except Exception:
            pass
    joined = "\n".join(texts)
    if "第一条" in joined or law_name in joined:
        return True, "found 第一条/name"
    return False, "no 第一条/name marker"

# law_name, [urls in priority order], meta
JOBS = [
    {
        "法规名": "无人驾驶航空器飞行管理暂行条例",
        "urls": ["https://www.caac.gov.cn/XXGK/XXGK/FLFG/202401/t20240115_222642.html"],
        "发布机关": "国务院、中央军事委员会",
        "文号": "国令第761号",
        "公布日期": "2023-06-28",
        "生效日期": "2024-01-01",
        "时效性": "现行有效",
        "备注": "seed页，全文含第一条至第六十三条",
    },
    {
        "法规名": "通用航空飞行管制条例",
        "urls": ["https://www.gov.cn/gongbao/content/2003/content_62599.htm",
                 "http://www.caac.gov.cn/XXGK/XXGK/FLFG/201510/t20151029_2794.html"],
        "发布机关": "国务院、中央军事委员会",
        "文号": "国务院、中央军委令第371号",
        "公布日期": "2003-01-10",
        "生效日期": "2003-05-01",
        "时效性": "现行有效",
        "备注": "国务院公报版",
    },
    {
        "法规名": "中华人民共和国民用航空器国籍登记条例",
        "urls": ["http://www.caac.gov.cn/XXGK/XXGK/FLFG/201510/t20151029_2790.html"],
        "发布机关": "国务院",
        "文号": "国务院令第232号",
        "公布日期": "1997-10-21",
        "生效日期": "1997-10-21",
        "时效性": "现行有效（2020年修订）",
        "备注": "民航局官网全文",
    },
    {
        "法规名": "外国民用航空器飞行管理规则",
        "urls": ["http://www.caac.gov.cn/XXGK/XXGK/FLFG/201510/t20151029_2793.html"],
        "发布机关": "国务院批准，中国民用航空总局发布",
        "文号": "国务院批准",
        "公布日期": "1979-02-23",
        "生效日期": "1979-02-23",
        "时效性": "现行有效（2019年修订）",
        "备注": "民航局官网全文",
    },
    {
        "法规名": "民用机场管理条例",
        "urls": ["https://www.gov.cn/gongbao/content/2009/content_1303629.htm",
                 "http://www.caac.gov.cn/XXGK/XXGK/FLFG/201510/t20151029_2785.html"],
        "发布机关": "国务院",
        "文号": "国务院令第553号",
        "公布日期": "2009-04-13",
        "生效日期": "2009-07-01",
        "时效性": "现行有效（2019年修订）",
        "备注": "国务院公报版",
    },
    {
        "法规名": "中华人民共和国测绘成果管理条例",
        "urls": ["https://www.gov.cn/gongbao/content/2006/content_334698.htm",
                 "https://www.gov.cn/ziliao/flfg/2006-06/07/content_302966.htm"],
        "发布机关": "国务院",
        "文号": "国务院令第469号",
        "公布日期": "2006-05-27",
        "生效日期": "2006-09-01",
        "时效性": "现行有效",
        "备注": "国务院公报版",
    },
    {
        "法规名": "中华人民共和国飞行基本规则",
        "urls": ["https://www.caac.gov.cn/XXGK/XXGK/FLFG/201510/t20151029_2792.html"],
        "发布机关": "国务院、中央军事委员会",
        "文号": "国务院、中央军委令第288号",
        "公布日期": "2000-07-24",
        "生效日期": "2001-08-01",
        "时效性": "现行有效（2001、2007年两次修订）",
        "备注": "民航局官网全文",
    },
    {
        "法规名": "中华人民共和国无线电管理条例",
        "urls": ["https://www.gov.cn/zhengce/content/2016-11/25/content_5137687.htm",
                 "https://www.miit.gov.cn/datainfo/fgk/gytxyxxhfg/xzfg/art/2020/art_9cf6a6c8f8e141c5868fa2c508f75f77.html"],
        "发布机关": "国务院、中央军事委员会",
        "文号": "国务院、中央军委令第672号",
        "公布日期": "2016-11-11",
        "生效日期": "2016-12-01",
        "时效性": "现行有效",
        "备注": "国务院令第672号修订版；无人机频谱相关",
    },
]

sess = make_session()
downloaded = []
failed = []

for job in JOBS:
    name = job["法规名"]
    ok = False
    last_err = ""
    tried = []
    for url in job["urls"]:
        tried.append(url)
        for attempt in range(2):
            try:
                r = sess.get(url, timeout=60, verify=False)
                if r.status_code != 200:
                    last_err = f"HTTP {r.status_code}"
                    continue
                content = r.content
                if len(content) <= 3072:
                    last_err = f"size too small {len(content)}"
                    continue
                ext = ext_from(url, content, r.headers.get("Content-Type"))
                good, reason = check_content(content, ext, name)
                if not good:
                    last_err = f"content check failed: {reason} (size {len(content)})"
                    continue
                fn, path = unique_path(name, ext)
                with open(path, "wb") as f:
                    f.write(content)
                sha = hashlib.sha256(content).hexdigest()
                downloaded.append({
                    "法规名": name,
                    "类别": "行政法规",
                    "效力层级": "行政法规",
                    "发布机关": job["发布机关"],
                    "文号": job["文号"],
                    "公布日期": job["公布日期"],
                    "生效日期": job["生效日期"],
                    "时效性": job["时效性"],
                    "源URL": url,
                    "本地文件名": fn,
                    "类型": ext.lstrip("."),
                    "字节数": len(content),
                    "sha256": sha,
                    "备注": job["备注"] + f"；校验:{reason}",
                })
                ok = True
                break
            except Exception as e:
                last_err = repr(e)
                time.sleep(1)
        if ok:
            break
    if not ok:
        failed.append({"法规名": name, "原因": last_err, "尝试URL": " | ".join(tried)})

result = {"downloaded": downloaded, "未获取": failed}
print(json.dumps(result, ensure_ascii=False, indent=1))
