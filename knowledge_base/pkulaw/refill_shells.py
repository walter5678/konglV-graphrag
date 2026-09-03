# -*- coding: utf-8 -*-
"""
refill_shells.py —— 对 diag_shells 识别出的"空壳"文件(shell_manifest.json)补抓实质内容：
  1) 判决书/案例页(/pfnl/)正文：扩展选择器 + 兜底"取页面最长文本块"
  2) 漏下的附件(如 docx)：重下 fjLink / resources.pkulaw 直链
产出：
  out/fulltext_online/<cli>.txt   (覆盖/补充登录态全文)
  out/attachments/<cli>/          (补下的附件)
  out/refill_report.json
"""
import os, sys, json, time, re
try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
SESS_DIR = os.path.join(HERE, ".edge_session")
OUT = os.path.join(HERE, "out")
SHELLS = os.path.join(OUT, "shell_manifest.json")
ATT_DIR = os.path.join(OUT, "attachments")
TXT_DIR = os.path.join(OUT, "fulltext_online")
LOGGED_OUT = ["剩余50%未阅读", "开通会员解锁全库", "已购买此数据库的VIP"]

# 正文抽取：先试容器选择器，再兜底取页面最长文本块
JS_EXTRACT = r"""
() => {
  const sels=['#divFullText','.PdfContent','#divContent','.detail-con','.text-con',
              '.fulltext','#Content','.content','#tab1','.pfnl-content','.article'];
  for (const s of sels){const e=document.querySelector(s); const t=e?(e.innerText||'').trim():''; if(t.length>300) return t;}
  let best='';
  document.querySelectorAll('div,article,section').forEach(e=>{
    const t=(e.innerText||'').trim();
    if(t.length>best.length && t.length<80000) best=t;
  });
  return best;
}
"""

def safe(name):
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()[:120] or "file"

def safe_content(page, tries=4):
    for _ in range(tries):
        try:
            return page.content()
        except Exception:
            time.sleep(1.5)
    return ""

def main():
    shells = json.load(open(SHELLS, encoding="utf-8"))
    # 去重(shell_manifest里docx项出现两次)
    seen, targets = set(), []
    for s in shells:
        if s["cli"] in seen:
            continue
        seen.add(s["cli"]); targets.append(s)
    print("空壳目标(去重):", len(targets), flush=True)

    os.makedirs(ATT_DIR, exist_ok=True); os.makedirs(TXT_DIR, exist_ok=True)
    report = []
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            SESS_DIR, channel="msedge", headless=False, accept_downloads=True,
            args=["--disable-blink-features=AutomationControlled"])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://www.pkulaw.com", wait_until="domcontentloaded", timeout=60000)
        time.sleep(2)

        for i, s in enumerate(targets, 1):
            cli, url = s["cli"], s["record_url"]
            rec = {"cli": cli, "title": s["title"], "body_len": 0, "attachments": []}
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                got = False
                for _ in range(6):
                    time.sleep(2)
                    html = safe_content(page)
                    if "【法宝引证码】" in html or page.query_selector("a.fjLink, a[href*='resources.pkulaw']") \
                       or page.query_selector("#divFullText, .PdfContent, #divContent"):
                        got = True; break
                if any(m in safe_content(page) for m in LOGGED_OUT):
                    rec["error"] = "logged_out"; report.append(rec)
                    print(f"  [{i}/{len(targets)}] {cli} ★掉登录", flush=True); continue
                # 正文
                body = ""
                try:
                    body = (page.evaluate(JS_EXTRACT) or "").strip()
                except Exception as e:
                    rec["extract_err"] = str(e)[:60]
                if len(body) >= 200:
                    with open(os.path.join(TXT_DIR, safe(cli) + ".txt"), "w", encoding="utf-8") as f:
                        f.write((s["title"] or "") + "\n\n" + body)
                    rec["body_len"] = len(body)
                # 附件
                links = page.eval_on_selector_all(
                    "a.fjLink, a[href*='resources.pkulaw']",
                    "els=>els.map(e=>({href:e.href, name:(e.innerText||'').trim()}))")
                uniq, seenh = [], set()
                for L in links:
                    if L["href"] and L["href"] not in seenh:
                        seenh.add(L["href"]); uniq.append(L)
                for L in uniq:
                    href = L["href"]; nm = safe(L["name"] or os.path.basename(href))
                    if not re.search(r"\.[a-zA-Z0-9]{2,5}$", nm):
                        nm += os.path.splitext(href.split("?")[0])[1] or ".bin"
                    try:
                        resp = ctx.request.get(href, headers={"Referer": url}, timeout=60000)
                        if resp.ok:
                            d = os.path.join(ATT_DIR, safe(cli)); os.makedirs(d, exist_ok=True)
                            with open(os.path.join(d, nm), "wb") as af:
                                af.write(resp.body())
                            rec["attachments"].append({"name": nm, "bytes": len(resp.body())})
                    except Exception as e:
                        rec["attachments"].append({"name": nm, "err": str(e)[:60]})
                report.append(rec)
                print(f"  [{i}/{len(targets)}] {cli} ｜ 正文{rec['body_len']}字 ｜ 附件{len(rec['attachments'])}", flush=True)
            except Exception as e:
                rec["error"] = str(e)[:100]; report.append(rec)
                print(f"  [{i}/{len(targets)}] {cli} ERROR {str(e)[:60]}", flush=True)
            time.sleep(1.2)
        try: ctx.close()
        except Exception: pass

    json.dump(report, open(os.path.join(OUT, "refill_report.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    ok = sum(1 for r in report if r["body_len"] >= 200 or r["attachments"])
    print(f"\n=== 补抓完成：{ok}/{len(targets)} 拿到正文或附件 ===", flush=True)
    print("报告 -> out/refill_report.json", flush=True)

if __name__ == "__main__":
    main()
