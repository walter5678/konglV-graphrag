# -*- coding: utf-8 -*-
"""
check_session.py —— 用已持久化的 .edge_session 打开测试record页，报告真实登录态+截图。
不做长等待；若已登录顺便dump附件UI。
"""
import os, sys, time, re
try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
SESS_DIR = os.path.join(HERE, ".edge_session")
TEST_URL = "https://www.pkulaw.com/lar/dacbdcf218cf668098a504dc405f5ccbbdfb.html"
LOGGED_OUT = ["剩余50%未阅读", "开通会员解锁全库", "已购买此数据库的VIP"]


def main():
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            SESS_DIR, channel="msedge", headless=False, accept_downloads=True,
            args=["--disable-blink-features=AutomationControlled"])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(TEST_URL, wait_until="domcontentloaded", timeout=60000)
        for _ in range(6):
            time.sleep(2.5)
            try: page.wait_for_load_state("networkidle", timeout=4000)
            except Exception: pass
            if "【法宝引证码】" in page.content(): break
        url = page.url
        html = page.content()
        out = not any(m in html for m in LOGGED_OUT) and "登录/注册" not in html and "【法宝引证码】" in html
        print("URL:", url, flush=True)
        print("HTML LEN:", len(html), flush=True)
        print("含'登录/注册':", "登录/注册" in html, flush=True)
        print("含会员墙标记:", [m for m in LOGGED_OUT if m in html], flush=True)
        print("含【法宝引证码】:", "【法宝引证码】" in html, flush=True)
        print("=> 登录态:", "√已登录" if out else "★未登录", flush=True)
        if out:
            print("---- 含'附件'元素 outerHTML ----", flush=True)
            seen = set()
            for e in page.query_selector_all("*"):
                try:
                    t = (e.inner_text() or "").strip()
                except Exception:
                    continue
                if t and "附件" in t and len(t) < 150:
                    oh = e.evaluate("el=>el.outerHTML")
                    k = oh[:100]
                    if len(oh) < 900 and k not in seen:
                        seen.add(k); print("  ", re.sub(r"\s+", " ", oh)[:700], flush=True)
            print("---- 下载/附件类元素 ----", flush=True)
            for e in page.query_selector_all(".fullDownload, .c-down, [class*=download], [class*=attach], [class*=Attach], [class*=fujian], [class*=Fujian]"):
                oh = e.evaluate("el=>el.outerHTML")
                print("  ", re.sub(r"\s+", " ", oh)[:300], flush=True)
        os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
        page.screenshot(path=os.path.join(HERE, "out", "check_shot.png"), full_page=True)
        print("截图 -> out/check_shot.png", flush=True)
        time.sleep(1)
        try: ctx.close()
        except Exception: pass


if __name__ == "__main__":
    main()
