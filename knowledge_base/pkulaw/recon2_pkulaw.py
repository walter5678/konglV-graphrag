# -*- coding: utf-8 -*-
"""
recon2_pkulaw.py —— 需先【完全关闭 Edge】。
复制登录Cookie到临时profile(不碰原profile)，用Playwright真实Edge打开带附件的record页，
验证登录态是否带过去，并dump附件下载入口的DOM结构。
"""
import os, sys, shutil, time, re
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
EDGE_UD = r"C:\Users\zy133\AppData\Local\Microsoft\Edge\User Data"
TMP_UD = os.path.join(HERE, ".edge_auto")
TEST_URL = "https://www.pkulaw.com/lar/dacbdcf218cf668098a504dc405f5ccbbdfb.html"  # 上海适飞空域(附件pdf)


def build_profile():
    os.makedirs(os.path.join(TMP_UD, "Default", "Network"), exist_ok=True)
    ok = {"Local State": False, "Cookies": False}
    src_ls = os.path.join(EDGE_UD, "Local State")
    if os.path.exists(src_ls):
        try:
            shutil.copy2(src_ls, os.path.join(TMP_UD, "Local State")); ok["Local State"] = True
        except Exception as e:
            print("Local State copy fail:", e)
    for fn in ["Cookies", "Cookies-wal"]:
        src = os.path.join(EDGE_UD, "Default", "Network", fn)
        if os.path.exists(src):
            try:
                with open(src, "rb") as f:
                    data = f.read()
                with open(os.path.join(TMP_UD, "Default", "Network", fn), "wb") as g:
                    g.write(data)
                if fn == "Cookies":
                    ok["Cookies"] = True
            except Exception as e:
                print("%s copy fail: %s" % (fn, e))
    return ok


def main():
    if os.path.exists(TMP_UD):
        shutil.rmtree(TMP_UD, ignore_errors=True)
    ok = build_profile()
    print("Cookie复制:", ok)
    if not ok["Cookies"]:
        print("!! Cookies复制失败——Edge可能仍在运行(文件被锁)。请彻底关闭Edge后重跑。")
        return
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            TMP_UD, channel="msedge", headless=False, accept_downloads=True,
            args=["--disable-blink-features=AutomationControlled"])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
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
        print("登录态判定:", "★未登录(仍是50%截断/会员墙)" if is_out else "√已登录(全文可见)")
        # 顶部用户区
        try:
            top = page.eval_on_selector("body", "b=>b.innerText").split("\n")
            head = [t for t in top[:8]]
            print("顶部文本:", head)
        except Exception: pass
        # dump 附件区
        print("---- 含'附件'元素 outerHTML ----")
        try:
            for e in page.query_selector_all("*"):
                t = (e.inner_text() or "").strip()
                if t and "附件" in t and len(t) < 120:
                    oh = e.evaluate("el=>el.outerHTML")
                    if len(oh) < 800:
                        print("  ", re.sub(r"\s+", " ", oh)[:500])
        except Exception as ex:
            print("dump err", ex)
        os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
        page.screenshot(path=os.path.join(HERE, "out", "recon2_shot.png"), full_page=True)
        print("截图 -> out/recon2_shot.png")
        time.sleep(1)
        try: ctx.close()
        except Exception: pass


if __name__ == "__main__":
    main()
