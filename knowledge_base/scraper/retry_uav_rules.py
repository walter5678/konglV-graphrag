# -*- coding: utf-8 -*-
"""重试 https 失败项（修正 SSL 上下文：关闭 check_hostname + CERT_NONE），合并进结果 JSON。"""
import os, re, sys, json, time, hashlib, ssl, requests
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

DIR_03 = r"D:\schoolwork\competition\低空经济无人机法律智能问答比赛\knowledge_base\law\03_部门规章"
DIR_04 = r"D:\schoolwork\competition\低空经济无人机法律智能问答比赛\knowledge_base\law\04_规范性文件"
HEADERS = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
           "Accept": "application/pdf,*/*"}

def make_session():
    s = requests.Session()
    from requests.adapters import HTTPAdapter
    from urllib3.util.ssl_ import create_urllib3_context
    class TLSAdapter(HTTPAdapter):
        def _ctx(self):
            ctx = create_urllib3_context()
            try: ctx.set_ciphers("DEFAULT@SECLEVEL=1")
            except Exception: pass
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return ctx
        def init_poolmanager(self, *a, **k):
            k["ssl_context"] = self._ctx(); return super().init_poolmanager(*a, **k)
        def proxy_manager_for(self, *a, **k):
            k["ssl_context"] = self._ctx(); return super().proxy_manager_for(*a, **k)
    s.mount("https://", TLSAdapter())
    return s

SESSION = make_session()
try: requests.packages.urllib3.disable_warnings()
except Exception: pass

def sanitize(n): return re.sub(r'[\\/:*?"<>|]', "_", n).strip()[:120]
def uniq(d, b, e):
    p = os.path.join(d, b + e); i = 1
    while os.path.exists(p): p = os.path.join(d, f"{b}_{i}{e}"); i += 1
    return p
def fetch(u):
    last = None
    for _ in range(2):
        try:
            r = SESSION.get(u, headers=HEADERS, timeout=60, verify=False); return r.status_code, r.content
        except Exception as e:
            last = e; time.sleep(2)
    raise last

# 4 个失败项（均 https）
RETRY = [
 {"法规名":"民用无人驾驶航空器运行安全管理规则(CCAR-92)","类别":"部门规章","效力层级":"部门规章",
  "发布机关":"交通运输部/中国民用航空局","文号":"交通运输部令2024年第1号（CCAR-92）",
  "公布日期":"2023-12-15","生效日期":"2024-01-01","时效性":"有效",
  "fname":"CCAR-92_民用无人驾驶航空器运行安全管理规则",
  "urls":["https://www.caac.gov.cn/XXGK/XXGK/MHGZ/202401/P020240103569247124102.pdf"],
  "备注":"seed；CCAR-92部部门规章，配套无人机飞行管理暂行条例"},
 {"法规名":"民用无人驾驶航空器操控员管理规定(AC-61-FS-020R3)","类别":"规范性文件","效力层级":"规范性文件(咨询通告)",
  "发布机关":"中国民用航空局飞行标准司","文号":"AC-61-FS-020R3",
  "公布日期":"2021-12-23","生效日期":"2021-12-23","时效性":"现行有效(最新版操控员管理规定)",
  "fname":"AC-61-FS-020R3_民用无人驾驶航空器操控员管理规定",
  "urls":["https://www.caac.gov.cn/PHONE/HDJL/YJZJ/202112/P020211223589109857888.pdf",
          "https://www.caac.gov.cn/HDJL/YJZJ/202112/P020211223589109857888.pdf"],
  "备注":"由《民用无人机驾驶员管理规定》AC-61-FS-2018-20R2更名修订而来，现行操控员执照管理依据"},
 {"法规名":"民用无人驾驶航空器实名制登记管理规定(AP-45-AA-2017-03)","类别":"规范性文件","效力层级":"规范性文件(管理程序)",
  "发布机关":"中国民用航空局航空器适航审定司","文号":"AP-45-AA-2017-03",
  "公布日期":"2017-05-16","生效日期":"2017-06-01","时效性":"已废止",
  "fname":"AP-45-AA-2017-03_民用无人驾驶航空器实名制登记管理规定",
  "urls":["https://www.caac.gov.cn/XXGK/XXGK/GFXWJ/201705/P020170517409761154678.pdf"],
  "备注":"seed HTML对应PDF附件；现已废止，被GB 46761-2025等替代"},
 {"法规名":"正常类多旋翼无人驾驶航空器系统适航标准(AC-21-AA-2026-46)","类别":"规范性文件","效力层级":"规范性文件(咨询通告)",
  "发布机关":"中国民用航空局航空器适航审定司","文号":"AC-21-AA-2026-46",
  "公布日期":"2026-04-03","生效日期":"2026-04-03","时效性":"有效",
  "fname":"AC-21-AA-2026-46_正常类多旋翼无人驾驶航空器系统适航标准",
  "urls":["https://www.caac.gov.cn/XXGK/XXGK/GFXWJ/202604/P020260417551228059844.pdf"],
  "备注":"正常类多旋翼(不载人)适航标准"},
]

RES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uav_rules_result.json")
data = json.load(open(RES, encoding="utf-8"))
done_names = {d["法规名"] for d in data["downloaded"]}

new_ok = []
for it in RETRY:
    d = DIR_03 if it["类别"]=="部门规章" else DIR_04
    ok=False; reason="";
    for u in it["urls"]:
        try: st, c = fetch(u)
        except Exception as e: reason=f"请求异常:{e}"; continue
        if st!=200: reason=f"HTTP {st}"; continue
        if len(c)<=3*1024: reason=f"仅{len(c)}字节"; continue
        if c[:5]!=b"%PDF-": reason="非PDF"; continue
        p = uniq(d, sanitize(it["fname"]), ".pdf")
        open(p,"wb").write(c)
        rec={"法规名":it["法规名"],"类别":it["类别"],"效力层级":it["效力层级"],"发布机关":it["发布机关"],
             "文号":it["文号"],"公布日期":it["公布日期"],"生效日期":it["生效日期"],"时效性":it["时效性"],
             "源URL":u,"本地文件名":os.path.basename(p),"类型":"PDF","字节数":len(c),
             "sha256":hashlib.sha256(c).hexdigest(),"备注":it["备注"]}
        new_ok.append(rec); print(f"OK {os.path.basename(p)} {len(c)}B"); ok=True; break
    if not ok: print(f"FAIL {it['法规名']} - {reason}")

# 合并：加入新成功项，从未获取移除
data["downloaded"].extend([r for r in new_ok if r["法规名"] not in done_names])
ok_names = {r["法规名"] for r in new_ok}
data["未获取"] = [f for f in data["未获取"] if f["法规名"] not in ok_names]
json.dump(data, open(RES,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
print("\n===RESULT_JSON===")
print(json.dumps(data, ensure_ascii=False))
