# -*- coding: utf-8 -*-
"""
recon_pkulaw.py —— 侦察：复制Edge登录Cookie到临时profile，用Playwright打开真实Edge
访问一个带附件的record页，判断登录态是否带过去、附件下载入口结构。
"""
import os, sys, shutil, time, json, re
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
EDGE_UD = r"C:\Users\zy133\AppData\Local\Microsoft\Edge\User Data"
TMP_UD = os.path.join(HERE, ".edge_auto")

TEST_URL = "https://www.pkulaw.com/lar/dacbdcf218cf668098a504dc405f5ccbbdfb.html"  # 上海适飞空域(有pdf附件)


def build_profile():
    """复制 Local State + Default 的关键登录文件到临时 user-data-dir。"""
    os.makedirs(os.path.join(TMP_UD, "Default", "Network"), exist_ok=True)
    # Local State（含cookie加密密钥）
    src_ls = os.path.join(EDGE_UD, "Local State")
    if os.path.exists(src_ls):
        shutil.copy2(src_ls, os.path.join(TMP_UD, "Local State"))
    # Cookies (+wal/journal)
    for fn in ["Cookies", "Cookies-wal", "Cookies-journal"]:
        src = os.path.join(EDGE_UD, "Default", "Network", fn)
        if os.path.exists(src):
            try:
                # 用共享读复制（Edge在运行时锁着）
                with open(src, "rb") as f:
                    data = f.read()
                with open(os.path.join(TMP_UD, "Default", "Network", fn), "wb") as g:
                    g.write(data)
            except Exception as e:
                print("copy fail", fn, e)
    # Preferences（可选）
    src_pref = os.path.join(EDGE_UD, "Default", "Preferences")
    if os.path.exists(src_pref):
        try:
            shutil.copy2(src_pref, os.path.join(TMP_UD, "Default", "Preferences"))
        except Exception as e:
            print("pref copy fail", e)


def main():
    if os.path.exists(TMP_UD):
        shutil.rmtree(TMP_UD, ignore_errors=True)
    build_profile()
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            TMP_UD, channel="msedge", headless=False,
            accept_downloads=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(TEST_URL, wait_until="domcontentloaded", timeout=60000)
        # 给反爬JS + 内容加载时间
        for _ in range(6):
            time.sleep(2.5)
            try:
                page.wait_for_load_state("networkidle", timeout=4000)
            except Exception:
                pass
            if "【法宝引证码】" in page.content() or "附件" in page.content():
                break
        html = page.content()
        print("FINAL URL:", page.url)
        print("TITLE:", page.title())
        print("HTML LEN:", len(html))
        for kw in ["请登录", "立即登录", "账号登录", "【法宝引证码】", "附件", "下载全文", "登录后"]:
            print("  含[%s]:" % kw, kw in html)
        # 抓 附件 相关元素
        print("---- 含'附件'的可点击元素 ----")
        try:
            els = page.query_selector_all("a, button, span, div")
            shown = 0
            for e in els:
                t = (e.inner_text() or "").strip()
                if t and ("附件" in t or "下载" in t) and len(t) < 60:
                    href = e.get_attribute("href")
                    onclick = e.get_attribute("onclick")
                    cls = e.get_attribute("class")
                    print("  <%s> text=%r href=%r onclick=%r class=%r" % (
                        e.evaluate("el=>el.tagName"), t[:40], href, (onclick or "")[:60], cls))
                    shown += 1
                    if shown > 25: break
        except Exception as e:
            print("query err", e)
        # 所有疑似附件直链
        hrefs = page.eval_on_selector_all("a", "els=>els.map(e=>e.href)")
        atts = [h for h in hrefs if re.search(r"\.(pdf|docx?|xlsx?|jpe?g|png|zip|rar)(\?|$)", h or "", re.I)
                or re.search(r"download|attach|file", h or "", re.I)]
        print("---- 疑似附件/下载 href ----")
        for h in list(dict.fromkeys(atts))[:20]:
            print("  ", h)
        page.screenshot(path=os.path.join(HERE, "out", "recon_shot.png"), full_page=True)
        print("截图 -> out/recon_shot.png")
        time.sleep(2)
        ctx.close()


if __name__ == "__main__":
    main()
