# -*- coding: utf-8 -*-
"""
download_attachments.py —— 用已登录的 .edge_session，对"缺正文"文件逐个打开record页，
抓 a.fjLink 附件直链并下载；顺带保存登录态下的全文文本(解决缺正文)。

用法:
    python download_attachments.py --limit 3          # 冒烟测试前3个
    python download_attachments.py                    # 全量(默认 short 集)
    python download_attachments.py --set attach       # 改跑"有附件"集(459)

输出:
    out/attachments/<CLI>/<文件名>          附件文件
    out/fulltext_online/<CLI>.txt           登录态全文(bonus)
    out/download_progress.json              进度(可断点续跑)
    out/download_report.md                  汇总
"""
import os, sys, json, time, re, argparse
try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
SESS_DIR = os.path.join(HERE, ".edge_session")
OUT = os.path.join(HERE, "out")
MANIFEST = os.path.join(OUT, "missing_body_manifest.json")
ATT_DIR = os.path.join(OUT, "attachments")
TXT_DIR = os.path.join(OUT, "fulltext_online")
PROG = os.path.join(OUT, "download_progress.json")

LOGGED_OUT = ["剩余50%未阅读", "开通会员解锁全库", "已购买此数据库的VIP"]


def safe_content(page, tries=4):
    """页面自动跳转时 content() 会抛错，重试。"""
    for _ in range(tries):
        try:
            return page.content()
        except Exception:
            time.sleep(1.5)
    return ""


def safe(name):
    name = re.sub(r'[\\/:*?"<>|]', "_", name).strip()
    return name[:120] or "file"


def load_progress():
    if os.path.exists(PROG):
        with open(PROG, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_progress(prog):
    with open(PROG, "w", encoding="utf-8") as f:
        json.dump(prog, f, ensure_ascii=False, indent=2)


def extract_body_text(page):
    """尽力取登录态正文文本。"""
    for sel in ["#divFullText", ".fulltext", "#Content", ".text-con", "#tab1"]:
        el = page.query_selector(sel)
        if el:
            try:
                t = el.inner_text().strip()
                if len(t) > 100:
                    return t
            except Exception:
                pass
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--set", default="short", choices=["short", "attach", "both"])
    args = ap.parse_args()

    with open(MANIFEST, encoding="utf-8") as f:
        rows = json.load(f)
    # 选择目标集
    def pick(r):
        if "error" in r or not r.get("record_url"):
            return False
        if args.set == "short":
            return r.get("short")
        if args.set == "attach":
            return r.get("has_attachment")
        return r.get("short") or r.get("has_attachment")
    targets = [r for r in rows if pick(r)]
    if args.limit:
        targets = targets[:args.limit]
    print("目标文件数:", len(targets), " (集合=%s)" % args.set, flush=True)

    os.makedirs(ATT_DIR, exist_ok=True)
    os.makedirs(TXT_DIR, exist_ok=True)
    prog = load_progress()

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            SESS_DIR, channel="msedge", headless=False, accept_downloads=True,
            args=["--disable-blink-features=AutomationControlled"])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        # 先验证登录态
        page.goto("https://www.pkulaw.com", wait_until="domcontentloaded", timeout=60000)
        time.sleep(2)

        n_att = n_done = n_noatt = n_fail = 0
        for i, r in enumerate(targets, 1):
            cli = r.get("cli") or ("row%d" % i)
            url = r["record_url"]
            if prog.get(cli, {}).get("done"):
                n_done += 1
                continue
            rec = {"cli": cli, "title": r.get("title"), "url": url, "attachments": [], "body_saved": False}
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                # 等待正文/附件出现
                got = False
                for _ in range(6):
                    time.sleep(2)
                    html = safe_content(page)
                    if "【法宝引证码】" in html or page.query_selector("a.fjLink, a[href*='resources.pkulaw']"):
                        got = True; break
                if any(m in safe_content(page) for m in LOGGED_OUT):
                    print("  [%d/%d] %s ★掉登录? 跳过" % (i, len(targets), cli), flush=True)
                    rec["error"] = "logged_out"
                    prog[cli] = rec; n_fail += 1
                    if i % 10 == 0: save_progress(prog)
                    continue
                # 抽附件直链：fjLink + 任何指向 resources.pkulaw 的链接（去重）
                links = page.eval_on_selector_all(
                    "a.fjLink, a[href*='resources.pkulaw']",
                    "els=>els.map(e=>({href:e.href, name:(e.innerText||'').trim()}))")
                uniq, seenh = [], set()
                for L in links:
                    if L["href"] and L["href"] not in seenh:
                        seenh.add(L["href"]); uniq.append(L)
                links = uniq
                # 0附件时记录调试：含'附件'字样的锚点
                if not links:
                    dbg = page.eval_on_selector_all(
                        "a", "els=>els.filter(e=>/附件|下载|\\.doc|\\.pdf|\\.xls|\\.zip/.test((e.innerText||'')+e.href)).map(e=>({t:(e.innerText||'').trim().slice(0,40),h:e.href,c:e.className}))")
                    rec["attach_debug"] = dbg[:8]
                # 存全文文本
                body = extract_body_text(page)
                if body:
                    with open(os.path.join(TXT_DIR, safe(cli) + ".txt"), "w", encoding="utf-8") as bf:
                        bf.write((r.get("title") or "") + "\n\n" + body)
                    rec["body_saved"] = True
                # 下载每个附件
                d = os.path.join(ATT_DIR, safe(cli))
                for L in links:
                    href = L["href"]; nm = safe(L["name"] or os.path.basename(href))
                    if not re.search(r"\.[a-zA-Z0-9]{2,5}$", nm):
                        ext = os.path.splitext(href.split("?")[0])[1] or ".bin"
                        nm += ext
                    try:
                        resp = ctx.request.get(href, headers={"Referer": url}, timeout=60000)
                        if resp.ok:
                            os.makedirs(d, exist_ok=True)
                            with open(os.path.join(d, nm), "wb") as af:
                                af.write(resp.body())
                            rec["attachments"].append({"name": nm, "href": href, "ok": True,
                                                        "bytes": len(resp.body())})
                            n_att += 1
                        else:
                            rec["attachments"].append({"name": nm, "href": href, "ok": False,
                                                        "status": resp.status})
                    except Exception as e:
                        rec["attachments"].append({"name": nm, "href": href, "ok": False,
                                                    "err": str(e)[:80]})
                if not links:
                    n_noatt += 1
                rec["done"] = True
                prog[cli] = rec
                print("  [%d/%d] %s ｜ 附件%d ｜ 全文%s" % (
                    i, len(targets), cli, len(links), "√" if rec["body_saved"] else "✗"), flush=True)
            except Exception as e:
                rec["error"] = str(e)[:120]
                prog[cli] = rec; n_fail += 1
                print("  [%d/%d] %s ERROR %s" % (i, len(targets), cli, str(e)[:80]), flush=True)
            if i % 5 == 0:
                save_progress(prog)
            time.sleep(1.2)  # 礼貌间隔
        save_progress(prog)
        try: ctx.close()
        except Exception: pass

    print("\n=== 汇总 ===", flush=True)
    print("已下载附件数:", n_att, " 无附件页:", n_noatt, " 跳过(已完成):", n_done, " 失败:", n_fail, flush=True)
    print("附件目录 ->", ATT_DIR, flush=True)


if __name__ == "__main__":
    main()
