# -*- coding: utf-8 -*-
import os, sys, io, re, hashlib, requests
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
import urllib3; urllib3.disable_warnings()
D=r"D:\schoolwork\competition\低空经济无人机法律智能问答比赛\knowledge_base\law\01_法律"
HEADERS={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"}
class TLS(HTTPAdapter):
    def init_poolmanager(self,*a,**k):
        c=create_urllib3_context()
        try:c.set_ciphers("DEFAULT@SECLEVEL=1")
        except Exception:pass
        c.check_hostname=False;k["ssl_context"]=c;return super().init_poolmanager(*a,**k)
S=requests.Session();S.mount("https://",TLS())
url="https://www.zqdzfy.gov.cn/uploads/ueditor/file/20250717/1752715145865271.pdf"
r=S.get(url,headers=HEADERS,timeout=90,verify=False)
b=r.content
print("HTTP",r.status_code,"bytes",len(b),"pdf?",b[:5]==b"%PDF-")
# verify text
import pdfplumber
txt=[]
with pdfplumber.open(io.BytesIO(b)) as pdf:
    npages=len(pdf.pages)
    for pg in pdf.pages:
        txt.append(pg.extract_text() or "")
full="\n".join(txt)
full_ns=re.sub(r"\s+","",full)
print("pages",npages,"chars",len(full_ns))
for kw in ["第四百五十二条","危害公共安全","扰乱公共秩序","高空抛物","2024年3月1日","刑法修正案"]:
    print(f"  含 {kw}: {kw.replace(' ','') in full_ns}")
# save if good
if r.status_code==200 and len(b)>3072 and b[:5]==b"%PDF-" and "第四百五十二条" in full_ns:
    # remove truncated html
    hp=os.path.join(D,"中华人民共和国刑法.html")
    if os.path.exists(hp): os.remove(hp); print("已删除截断的HTML")
    p=os.path.join(D,"中华人民共和国刑法.pdf")
    open(p,"wb").write(b)
    print("SAVED 中华人民共和国刑法.pdf bytes",len(b))
    print("SHA256",hashlib.sha256(b).hexdigest())
else:
    print("PDF校验未通过，未保存")