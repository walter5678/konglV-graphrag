# -*- coding: utf-8 -*-
"""
下载民航局【部门规章(CCAR)】与【规范性文件/咨询通告(AC/MD/IB/AP)】中涉无人机的官方原始文件。
原始字节直写；PDF 存 .pdf / HTML 存 .html；核验 + SHA256；输出汇总 JSON。
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

DIR_03 = r"D:\schoolwork\competition\低空经济无人机法律智能问答比赛\knowledge_base\law\03_部门规章"
DIR_04 = r"D:\schoolwork\competition\低空经济无人机法律智能问答比赛\knowledge_base\law\04_规范性文件"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/pdf,*/*",
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
                k["ssl_context"] = ctx
                return super().init_poolmanager(*a, **k)

            def proxy_manager_for(self, *a, **k):
                ctx = create_urllib3_context()
                try:
                    ctx.set_ciphers("DEFAULT@SECLEVEL=1")
                except Exception:
                    pass
                k["ssl_context"] = ctx
                return super().proxy_manager_for(*a, **k)

        s.mount("https://", TLSAdapter())
    except Exception:
        pass
    return s


SESSION = make_session()


def sanitize(name):
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name.strip()[:120]


def unique_path(directory, base, ext):
    p = os.path.join(directory, base + ext)
    i = 1
    while os.path.exists(p):
        p = os.path.join(directory, f"{base}_{i}{ext}")
        i += 1
    return p


def fetch(url):
    """下载原始字节，超时60，失败重试1次；返回 (status, content)。"""
    last = None
    for attempt in range(2):
        try:
            r = SESSION.get(url, headers=HEADERS, timeout=60, verify=False)
            return r.status_code, r.content
        except Exception as e:
            last = e
            time.sleep(2)
    raise last


def validate(content, ftype, name):
    if len(content) <= 3 * 1024:
        return False, f"大小仅{len(content)}字节(<3KB)"
    if ftype == "pdf":
        if content[:5] != b"%PDF-":
            return False, "非PDF(缺少%PDF头)"
        return True, ""
    else:  # html
        try:
            text = content.decode("utf-8", "ignore")
        except Exception:
            text = ""
        key = name[:6]
        if re.search(r"第\s*[0-9一二三四五六七八九十百]+\s*条", text) or key in text:
            return True, ""
        return False, "HTML未含『第X条』或法规名"


# ---------------------------------------------------------------------------
# 下载清单：url + 若干 fallback；类别决定保存目录
# ---------------------------------------------------------------------------
ITEMS = [
    # ===== 部门规章 -> 03 =====
    {
        "法规名": "民用无人驾驶航空器运行安全管理规则(CCAR-92)",
        "类别": "部门规章", "效力层级": "部门规章",
        "发布机关": "交通运输部/中国民用航空局",
        "文号": "交通运输部令2024年第1号（CCAR-92）",
        "公布日期": "2023-12-15", "生效日期": "2024-01-01", "时效性": "有效",
        "ftype": "pdf", "fname": "CCAR-92_民用无人驾驶航空器运行安全管理规则",
        "urls": ["https://www.caac.gov.cn/XXGK/XXGK/MHGZ/202401/P020240103569247124102.pdf"],
        "备注": "seed；CCAR-92部部门规章，配套无人机飞行管理暂行条例",
    },
    {
        "法规名": "一般运行和飞行规则(CCAR-91-R4)",
        "类别": "部门规章", "效力层级": "部门规章",
        "发布机关": "交通运输部/中国民用航空局",
        "文号": "交通运输部令2022年第3号（CCAR-91-R4）",
        "公布日期": "2022-02-09", "生效日期": "2022-07-01", "时效性": "有效",
        "ftype": "pdf", "fname": "CCAR-91-R4_一般运行和飞行规则",
        "urls": ["http://www.caac.gov.cn/XXGK/XXGK/MHGZ/202202/P020220209518466960506.pdf"],
        "备注": "通用航空一般运行规则，无人机运行的上位规章依据",
    },

    # ===== 规范性文件 / 咨询通告 -> 04 =====
    {
        "法规名": "民用无人驾驶航空器操控员管理规定(AC-61-FS-020R3)",
        "类别": "规范性文件", "效力层级": "规范性文件(咨询通告)",
        "发布机关": "中国民用航空局飞行标准司",
        "文号": "AC-61-FS-020R3",
        "公布日期": "2021-12-23", "生效日期": "2021-12-23", "时效性": "现行有效(最新版操控员管理规定)",
        "ftype": "pdf", "fname": "AC-61-FS-020R3_民用无人驾驶航空器操控员管理规定",
        "urls": ["https://www.caac.gov.cn/PHONE/HDJL/YJZJ/202112/P020211223589109857888.pdf",
                 "https://www.caac.gov.cn/HDJL/YJZJ/202112/P020211223589109857888.pdf"],
        "备注": "由《民用无人机驾驶员管理规定》AC-61-FS-2018-20R2 更名修订而来，现行操控员执照管理依据",
    },
    {
        "法规名": "民用无人驾驶航空器实名制登记管理规定(AP-45-AA-2017-03)",
        "类别": "规范性文件", "效力层级": "规范性文件(管理程序)",
        "发布机关": "中国民用航空局航空器适航审定司",
        "文号": "AP-45-AA-2017-03",
        "公布日期": "2017-05-16", "生效日期": "2017-06-01", "时效性": "已废止",
        "ftype": "pdf", "fname": "AP-45-AA-2017-03_民用无人驾驶航空器实名制登记管理规定",
        "urls": ["https://www.caac.gov.cn/XXGK/XXGK/GFXWJ/201705/P020170517409761154678.pdf"],
        "备注": "seed HTML对应PDF附件；现已废止，被GB 46761-2025等替代",
    },
    {
        "法规名": "民用无人驾驶航空器系统空中交通管理办法(MD-TM-2016-004)",
        "类别": "规范性文件", "效力层级": "规范性文件",
        "发布机关": "中国民用航空局空管行业管理办公室",
        "文号": "MD-TM-2016-004",
        "公布日期": "2016-09-21", "生效日期": "2016-09-21", "时效性": "有效",
        "ftype": "pdf", "fname": "MD-TM-2016-004_民用无人驾驶航空器系统空中交通管理办法",
        "urls": ["http://www.caac.gov.cn/XXGK/XXGK/GFXWJ/201610/P020161008345668760913.pdf",
                 "http://www.caac.gov.cn/PHONE/XXGK_17/XXGK/GFXWJ/201610/P020161008345668760913.pdf"],
        "备注": "无人机系统空中交通管理(隔离空域等)",
    },
    {
        "法规名": "民用无人驾驶航空器经营性飞行活动管理办法(暂行)(MD-TR-2018-01)",
        "类别": "规范性文件", "效力层级": "规范性文件",
        "发布机关": "中国民用航空局运输司",
        "文号": "MD-TR-2018-01",
        "公布日期": "2018-03-21", "生效日期": "2018-06-01", "时效性": "有效",
        "ftype": "pdf", "fname": "MD-TR-2018-01_民用无人驾驶航空器经营性飞行活动管理办法(暂行)",
        "urls": ["http://www.caac.gov.cn/XXGK/XXGK/GFXWJ/201804/P020180409336678475193.pdf"],
        "备注": "seed",
    },
    {
        "法规名": "轻小无人机运行规定(试行)(AC-91-FS-2015-31)",
        "类别": "规范性文件", "效力层级": "规范性文件(咨询通告)",
        "发布机关": "中国民用航空局飞行标准司",
        "文号": "AC-91-FS-2015-31",
        "公布日期": "2015-12-29", "生效日期": "2015-12-29", "时效性": "有效",
        "ftype": "pdf", "fname": "AC-91-FS-2015-31_轻小无人机运行规定(试行)",
        "urls": ["http://www.caac.gov.cn/XXGK/XXGK/GFXWJ/201601/P020170527591647559640.pdf"],
        "备注": "依据CCAR-91部制定的轻小无人机运行规定",
    },
    {
        "法规名": "民用无人驾驶航空器系统适航审定管理程序(AP-21-AA-2022-71)",
        "类别": "规范性文件", "效力层级": "规范性文件(管理程序)",
        "发布机关": "中国民用航空局航空器适航审定司",
        "文号": "民航规〔2022〕64号；AP-21-AA-2022-71",
        "公布日期": "2022-12-19", "生效日期": "2022-12-19", "时效性": "有效",
        "ftype": "pdf", "fname": "AP-21-AA-2022-71_民用无人驾驶航空器系统适航审定管理程序",
        "urls": ["http://www.caac.gov.cn/XXGK/XXGK/GFXWJ/202302/P020230213509928643135.pdf"],
        "备注": "无人机适航审定核心管理程序",
    },
    {
        "法规名": "中型民用无人驾驶航空器系统适航标准及符合性指导材料(试行)(AC-92-AA-2024-02)",
        "类别": "规范性文件", "效力层级": "规范性文件(咨询通告)",
        "发布机关": "中国民用航空局航空器适航审定司",
        "文号": "民航适函〔2024〕52号；AC-92-AA-2024-02",
        "公布日期": "2024-07-23", "生效日期": "2024-07-23", "时效性": "有效",
        "ftype": "pdf", "fname": "AC-92-AA-2024-02_中型民用无人驾驶航空器系统适航标准及符合性指导材料(试行)",
        "urls": ["http://www.caac.gov.cn/XXGK/XXGK/GFXWJ/202408/P020240807518082185594.pdf"],
        "备注": "中型无人机适航标准",
    },
    {
        "法规名": "民用无人驾驶航空器运行控制系统要求(AC-92-FS-002)",
        "类别": "规范性文件", "效力层级": "规范性文件(咨询通告)",
        "发布机关": "中国民用航空局",
        "文号": "民航规〔2026〕2号；AC-92-FS-002",
        "公布日期": "2026-01-16", "生效日期": "2026-01-16", "时效性": "有效",
        "ftype": "pdf", "fname": "AC-92-FS-002_民用无人驾驶航空器运行控制系统要求",
        "urls": ["http://www.caac.gov.cn/XXGK/XXGK/GFXWJ/202602/P020260202589788681151.pdf"],
        "备注": "CCAR-92部配套，运行控制系统功能要求",
    },
    {
        "法规名": "限用类无人驾驶航空器系统适航标准(AC-21-AA-2026-44)",
        "类别": "规范性文件", "效力层级": "规范性文件(咨询通告)",
        "发布机关": "中国民用航空局航空器适航审定司",
        "文号": "AC-21-AA-2026-44",
        "公布日期": "2026-02-12", "生效日期": "2026-02-12", "时效性": "有效",
        "ftype": "pdf", "fname": "AC-21-AA-2026-44_限用类无人驾驶航空器系统适航标准",
        "urls": ["http://www.caac.gov.cn/XXGK/XXGK/GFXWJ/202602/P020260226338705668572.pdf"],
        "备注": "CCAR-92部第92.343条限用类适航要求",
    },
    {
        "法规名": "正常类多旋翼无人驾驶航空器系统适航标准(AC-21-AA-2026-46)",
        "类别": "规范性文件", "效力层级": "规范性文件(咨询通告)",
        "发布机关": "中国民用航空局航空器适航审定司",
        "文号": "AC-21-AA-2026-46",
        "公布日期": "2026-04-03", "生效日期": "2026-04-03", "时效性": "有效",
        "ftype": "pdf", "fname": "AC-21-AA-2026-46_正常类多旋翼无人驾驶航空器系统适航标准",
        "urls": ["https://www.caac.gov.cn/XXGK/XXGK/GFXWJ/202604/P020260417551228059844.pdf"],
        "备注": "正常类多旋翼(不载人)适航标准",
    },
    {
        "法规名": "正常类动力提升无人驾驶航空器系统适航标准(AC-21-AA-2026-47)",
        "类别": "规范性文件", "效力层级": "规范性文件(咨询通告)",
        "发布机关": "中国民用航空局航空器适航审定司",
        "文号": "AC-21-AA-2026-47",
        "公布日期": "2026-04-03", "生效日期": "2026-04-03", "时效性": "有效",
        "ftype": "pdf", "fname": "AC-21-AA-2026-47_正常类动力提升无人驾驶航空器系统适航标准",
        "urls": ["http://www.caac.gov.cn/XXGK/XXGK/GFXWJ/202604/P020260417552626968757.pdf",
                 "http://www.caac.gov.cn/PHONE/XXGK_17/XXGK/GFXWJ/202604/P020260417552626968757.pdf"],
        "备注": "正常类动力提升(不载人)适航标准",
    },
    {
        "法规名": "D类限用类民用无人驾驶航空器系统失效状态(AC-21-AA-2022-40)",
        "类别": "规范性文件", "效力层级": "规范性文件(咨询通告)",
        "发布机关": "中国民用航空局航空器适航审定司",
        "文号": "民航适发〔2022〕18号；AC/21/AA/2022/40",
        "公布日期": "2022-12-21", "生效日期": "2022-12-21", "时效性": "有效",
        "ftype": "pdf", "fname": "AC-21-AA-2022-40_D类限用类无人驾驶航空器系统失效状态",
        "urls": ["http://www.caac.gov.cn/XXGK/XXGK/GFXWJ/202302/P020230213505366854054.pdf"],
        "备注": "最大审定起飞重量≤5700kg的D类限用类无人机失效状态",
    },
    {
        "法规名": "无人驾驶航空器系统相关信息通告(IB-TM-2022-05)",
        "类别": "规范性文件", "效力层级": "规范性文件(信息通告)",
        "发布机关": "民航局飞行标准司/适航审定司/空管行业管理办公室",
        "文号": "IB-TM-2022-05",
        "公布日期": "2022-09-21", "生效日期": "2022-09-21", "时效性": "有效",
        "ftype": "pdf", "fname": "IB-TM-2022-05_无人驾驶航空器系统信息通告",
        "urls": ["http://www.caac.gov.cn/XXGK/XXGK/GFXWJ/202209/P020220921337984338794.pdf"],
        "备注": "三司局联合信息通告",
    },
]


def main():
    try:
        requests.packages.urllib3.disable_warnings()
    except Exception:
        pass

    downloaded, failed = [], []
    for it in ITEMS:
        directory = DIR_03 if it["类别"] == "部门规章" else DIR_04
        os.makedirs(directory, exist_ok=True)
        ext = ".pdf" if it["ftype"] == "pdf" else ".html"
        base = sanitize(it["fname"])

        ok = False
        last_reason, used_url = "", ""
        for url in it["urls"]:
            used_url = url
            try:
                status, content = fetch(url)
            except Exception as e:
                last_reason = f"请求异常:{e}"
                continue
            if status != 200:
                last_reason = f"HTTP {status}"
                continue
            valid, reason = validate(content, it["ftype"], it["法规名"])
            if not valid:
                last_reason = reason
                continue
            path = unique_path(directory, base, ext)
            with open(path, "wb") as f:
                f.write(content)
            sha = hashlib.sha256(content).hexdigest()
            downloaded.append({
                "法规名": it["法规名"], "类别": it["类别"], "效力层级": it["效力层级"],
                "发布机关": it["发布机关"], "文号": it["文号"],
                "公布日期": it["公布日期"], "生效日期": it["生效日期"], "时效性": it["时效性"],
                "源URL": url, "本地文件名": os.path.basename(path),
                "类型": it["ftype"].upper(), "字节数": len(content), "sha256": sha,
                "备注": it["备注"],
            })
            print(f"OK  {os.path.basename(path)}  {len(content)}B")
            ok = True
            break
        if not ok:
            failed.append({"法规名": it["法规名"], "原因": last_reason,
                           "尝试URL": " | ".join(it["urls"])})
            print(f"FAIL {it['法规名']} - {last_reason}")
        time.sleep(1)

    result = {"downloaded": downloaded, "未获取": failed}
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uav_rules_result.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("\n===RESULT_JSON===")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
