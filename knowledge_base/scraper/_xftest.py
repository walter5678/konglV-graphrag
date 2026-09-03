# -*- coding: utf-8 -*-
import sys, re, time, requests
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
import urllib3; urllib3.disable_warnings()
HEADERS={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36","Accept-Language":"zh-CN,zh;q=0.9"}
class TLS(HTTPAdapter):
    def init_poolmanager(self,*a,**k):
        c=create_urllib3_context()
        try:c.set_ciphers("DEFAULT@SECLEVEL=1")
        except Exception:pass
        c.check_hostname=False;k["ssl_context"]=c;return super().init_poolmanager(*a,**k)
S=requests.Session();S.mount("https://",TLS())
urls=[
 "https://www.spp.gov.cn/spp/fl/201802/t20180206_364975.shtml",
 "https://www.shanwei.gov.cn/swssjj/gkmlpt/content/0/937/post_937820.html",
 "https://www.zqdzfy.gov.cn/uploads/ueditor/file/20250717/1752715145865271.pdf",
]
ART=re.compile(r"第[一二三四五六七八九十百]+条")
for u in urls:
    try:
        r=S.get(u,headers=HEADERS,timeout=60,verify=False)
    except Exception as e:
        print("REQFAIL",u,e);continue
    b=r.content
    if u.endswith(".pdf"):
        print(f"{r.status_code} {len(b)}B PDF head={b[:5]}  {u}");continue
    t=None
    for enc in("utf-8","gb18030"):
        try:
            tt=b.decode(enc)
            if "刑罚" in tt or "第一条" in tt: t=tt;break
        except Exception:pass
    if t is None:t=b.decode("utf-8","ignore")
    p=re.sub(r"<[^>]+>"," ",t)
    last452="第四百五十二条" in p
    # detect 修正案12-era edits: 第一百六十五条第二款 mentions 其他公司、企业 董事、监事
    amd12 = "其他公司、企业的董事、监事" in p or "帮助信息网络犯罪活动" in p
    amd11 = "高空抛物" in p or "冒名顶替" in p
    print(f"{r.status_code} {len(b)}B 条数={len(ART.findall(p))} 末条452={last452} 修11痕迹={amd11} 修12痕迹={amd12}  {u}")
    time.sleep(1)