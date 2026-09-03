# -*- coding: utf-8 -*-
"""
recon3_pkulaw.py —— 需先【完全关闭 Edge】。
直接用 Playwright 启动【真实 Default profile】(不复制)，靠Edge自身解密Cookie拿到登录态。
打开带附件的record页，验证登录态，dump附件下载入口。
"""
import os, sys, time, re
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
EDGE_UD = r"C:\Users\zy133\AppData\Local\Microsoft\Edge\User Data"
TEST_URL = "https://www.pkulaw.com/lar/dacbdcf218cf668098a504dc405f5ccbbdfb.html"


def main():
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            EDGE_UD, channel="msedge", headless=False, accept_downloads=True,
            args=["--disable-blink-features=AutomationControlled",
                  "--profile-directory=Default"])
        page = ctx.new_page()
        page.goto(TEST_URL, wait_until="domcontentloaded", timeout=60000)
        for _ in range(6):
            time.sleep(2.5)
            try: page.wait_for_load_state("networkidle", timeout=4000)
            except Exception: pass
            if "附件" in page.content(): break
        html = page.content()
        logged_out_marks = ["剩余50%未阅读", "继续阅读", "开通会员解锁全库", "已购买此数据库的VIP"]
        is_out = any(m in html for m in logged_out_marks)
        print("HTML LEN:", len(html))
        print("登录态判定:", "★未登录" if is_out else "√已登录(全文可见)")
        # 顶部用户名区（登录后通常显示用户名/机构名而非"登录/注册"）
        try:
            body_txt = page.eval_on_selector("body", "b=>b.innerText")
            print("顶部含'登录/注册':", "登录/注册" in body_txt[:400])
        except Exception: pass
        # dump 附件区 outerHTML
        print("---- 含'附件'元素 outerHTML(<800字) ----")
        seen = set()
        try:
            for e in page.query_selector_all("*"):
                t = (e.inner_text() or "").strip()
                if t and "附件" in t and len(t) < 150:
                    oh = e.evaluate("el=>el.outerHTML")
                    key = oh[:80]
                    if len(oh) < 800 and key not in seen:
                        seen.add(key)
                        print("  ", re.sub(r"\s+", " ", oh)[:600])
        except Exception as ex:
            print("dump err", ex)
        # 顶部"下载"工具元素
        print("---- '下载'工具元素 ----")
        try:
            for e in page.query_selector_all(".fullDownload, .c-down, [class*=download]"):
                oh = e.evaluate("el=>el.outerHTML")
                print("  ", re.sub(r"\s+", " ", oh)[:300])
        except Exception: pass
        os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
        page.screenshot(path=os.path.join(HERE, "out", "recon3_shot.png"), full_page=True)
        print("截图 -> out/recon3_shot.png")
        time.sleep(1)
        try: ctx.close()
        except Exception: pass


if __name__ == "__main__":
    main()
