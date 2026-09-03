# -*- coding: utf-8 -*-
import os, sys, re, time, hashlib, requests
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
import urllib3; urllib3.disable_warnings()

D = r"D:\schoolwork\competition\低空经济无人机法律智能问答比赛\knowledge_base\law\01_法律"
HEADERS = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
           "Accept":"text/html,application/xhtml+xml,application/pdf,*/*;q=0.8","Accept-Language":"zh-CN,zh;q=0.9"}
class TLS(HTTPAdapter):
    def init_poolmanager(self,*a,**k):
        ctx=create_urllib3_context()
        try: ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        except Exception: pass
        ctx.check_hostname=False; k["ssl_context"]=ctx
        return super().init_poolmanager(*a,**k)
S=requests.Session(); S.mount("https://",TLS())

JOBS = [
 {"name":"中华人民共和国测绘法","kw":"测绘","urls":[
    "http://www.npc.gov.cn/zgrdw/npc/xinwen/2017-04/27/content_2020927.htm",
    "http://www.gd.gov.cn/zwgk/wjk/zcfgk/content/post_2521574.html",
    "https://zrzyt.xinjiang.gov.cn/xjgtzy/c108899/202209/63babb2b1b744bdfaca6278c124902e9.shtml",
 ]},
 {"name":"中华人民共和国国家安全法","kw":"国家安全","urls":[
    "https://npc.gov.cn/zgrdw/npc/xinwen/2015-07/07/content_1941161.htm",
    "https://www.stats.gov.cn/gk/tjfg/xgfxfg/202503/t20250310_1958929.html",
    "https://nnsa.mee.gov.cn/ztzl/haqshmhsh/qmgjanjyr/ztgjaqg/202406/P020240624425032863498.pdf",
 ]},
]
ART = re.compile(r"第[一二三四五六七八九十百千零两]+条")
def get(u):
    for _ in range(2):
        try: return S.get(u,headers=HEADERS,timeout=60,verify=False)
        except Exception as e: last=str(e); time.sleep(2)
    return None
def content_ok(b,kw,is_pdf):
    if is_pdf: return b[:5]==b"%PDF-" and len(b)>3072
    for enc in ("utf-8","gb18030"):
        try: t=b.decode(enc)
        except Exception: continue
        plain=re.sub(r"<[^>]+>"," ",t)
        if kw in plain and len(ART.findall(plain))>=5 and ("第一条" in plain):
            return True
    return False
for j in JOBS:
    print("\n===",j["name"],"===")
    done=False
    for u in j["urls"]:
        r=get(u)
        if r is None: print("  x req fail",u); continue
        b=r.content; is_pdf=u.lower().endswith(".pdf")
        print(f"  {u} -> {r.status_code} {len(b)}B")
        if r.status_code!=200 or len(b)<=3072: continue
        if not content_ok(b,j["kw"],is_pdf):
            print("     内容校验失败(空壳/无正文)"); continue
        ext="pdf" if is_pdf else "html"
        fn=j["name"]+"."+ext
        open(os.path.join(D,fn),"wb").write(b)
        sha=hashlib.sha256(b).hexdigest()
        print(f"     OK saved {fn} {len(b)}B ext={ext}")
        print(f"     URL={u}")
        print(f"     SHA256={sha}")
        print(f"     条数={len(ART.findall(re.sub(chr(60)+'[^'+chr(62)+']*'+chr(62),' ', b.decode('utf-8','ignore')))) if not is_pdf else 'pdf'}")
        done=True; break
    if not done: print("  !! 全部候选失败")