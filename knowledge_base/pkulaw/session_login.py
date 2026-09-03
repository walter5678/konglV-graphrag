# -*- coding: utf-8 -*-
"""
session_login.py —— 用独立profile启动Edge，等用户手动登录pkulaw，检测成功后dump附件UI。
会话持久化在 .edge_session/，供后续批量下载复用（无需再登录）。
在自动化窗口里手动登录即可（右上角 登录/注册）。
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
MAX_WAIT = 600  # 秒


def is_logged_in(page):
    """严格判据：必须回到pkulaw域名 + 顶部无'登录/注册' + 有正文引证码 + 无会员墙标记。"""
    try:
        url = page.url or ""
        if "pkulaw.com" not in url:      # 还停在CARSI/学校IdP等中转页
            return False
        html = page.content()
    except Exception:
        return False
    if any(m in html for m in LOGGED_OUT):
        return False
    if "登录/注册" in html:
        return False
    if "【法宝引证码】" not in html:       # 正文未真正加载出来
        return False
    return True


def main():
    os.makedirs(SESS_DIR, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            SESS_DIR, channel="msedge", headless=False, accept_downloads=True,
            args=["--disable-blink-features=AutomationControlled"])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(TEST_URL, wait_until="domcontentloaded", timeout=60000)
        print(">>> 请在弹出的 Edge 窗口里登录 pkulaw（右上角 登录/注册）。等待检测…", flush=True)
        t0 = time.time()
        logged = False
        while time.time() - t0 < MAX_WAIT:
            time.sleep(4)
            try:
                if is_logged_in(page):
                    logged = True
                    break
            except Exception:
                pass
            # 只有当已回到 pkulaw 域名、但仍显示未登录时，才重载刷新登录态。
            # 若还停在 CARSI/学校认证页，绝不重载（否则会打断登录输入）。
            try:
                cur = page.url or ""
            except Exception:
                cur = ""
            if "pkulaw.com" in cur and int(time.time() - t0) % 16 < 4:
                try:
                    page.reload(wait_until="domcontentloaded", timeout=30000)
                except Exception:
                    pass
            print("  …等待登录中 (%ds)" % int(time.time() - t0), flush=True)
        if not logged:
            print("!! 超时未检测到登录。窗口保持打开，可再登录后重跑。", flush=True)
            try: ctx.close()
            except Exception: pass
            return
        print("√ 已登录！开始侦察附件UI…", flush=True)
        time.sleep(2)
        try: page.wait_for_load_state("networkidle", timeout=8000)
        except Exception: pass
        html = page.content()
        print("HTML LEN:", len(html), flush=True)
        # dump 含'附件'元素
        print("---- 含'附件'元素 outerHTML(<900字) ----", flush=True)
        seen = set()
        try:
            for e in page.query_selector_all("*"):
                t = (e.inner_text() or "").strip()
                if t and "附件" in t and len(t) < 150:
                    oh = e.evaluate("el=>el.outerHTML")
                    key = oh[:100]
                    if len(oh) < 900 and key not in seen:
                        seen.add(key)
                        print("  ", re.sub(r"\s+", " ", oh)[:700], flush=True)
        except Exception as ex:
            print("dump err", ex, flush=True)
        # 下载工具元素
        print("---- '下载'工具元素 ----", flush=True)
        try:
            for e in page.query_selector_all(".fullDownload, .c-down, [class*=download], [class*=attach], [class*=Attach]"):
                oh = e.evaluate("el=>el.outerHTML")
                print("  ", re.sub(r"\s+", " ", oh)[:300], flush=True)
        except Exception: pass
        os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
        page.screenshot(path=os.path.join(HERE, "out", "recon_login_shot.png"), full_page=True)
        print("截图 -> out/recon_login_shot.png", flush=True)
        print("SESSION_READY", flush=True)
        time.sleep(2)
        try: ctx.close()
        except Exception: pass


if __name__ == "__main__":
    main()
