# -*- coding: utf-8 -*-
import sys, os, re, hashlib, json
import requests
from requests.adapters import HTTPAdapter
try:
    from urllib3.util.ssl_ import create_urllib3_context
except Exception:
    from urllib3.util.ssl_ import create_urllib3_context

SAVE_DIR = r"D:\schoolwork\competition\低空经济无人机法律智能问答比赛\knowledge_base\law\05_标准"

class SSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *a, **k):
        ctx = create_urllib3_context(ciphers='DEFAULT@SECLEVEL=1')
        try:
            ctx.check_hostname = False
        except Exception:
            pass
        import ssl as _ssl
        ctx.verify_mode = _ssl.CERT_NONE
        k['ssl_context'] = ctx
        return super().init_poolmanager(*a, **k)
    def proxy_manager_for(self, *a, **k):
        ctx = create_urllib3_context(ciphers='DEFAULT@SECLEVEL=1')
        import ssl as _ssl
        ctx.check_hostname = False
        ctx.verify_mode = _ssl.CERT_NONE
        k['ssl_context'] = ctx
        return super().proxy_manager_for(*a, **k)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

def make_session():
    s = requests.Session()
    s.mount('https://', SSLAdapter())
    s.mount('http://', SSLAdapter())
    s.headers.update({'User-Agent': UA})
    return s

def sanitize(name):
    name = re.sub(r'[\\/:*?"<>|]+', '_', name)
    return name.strip()

def unique_path(fn):
    path = os.path.join(SAVE_DIR, fn)
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(fn)
    i = 2
    while True:
        p = os.path.join(SAVE_DIR, f"{base}_{i}{ext}")
        if not os.path.exists(p):
            return p
        i += 1

def download(url, fn, referer=None):
    s = make_session()
    headers = {}
    if referer:
        headers['Referer'] = referer
    last = None
    for attempt in range(2):
        try:
            r = s.get(url, headers=headers, timeout=60, verify=False)
            data = r.content
            status = r.status_code
            ok = (status == 200 and len(data) > 10240 and data[:4] == b'%PDF')
            if ok:
                path = unique_path(sanitize(fn))
                with open(path, 'wb') as f:
                    f.write(data)
                sha = hashlib.sha256(data).hexdigest()
                return {"ok": True, "path": path, "fn": os.path.basename(path),
                        "size": len(data), "sha256": sha, "status": status}
            else:
                last = {"ok": False, "status": status, "size": len(data),
                        "head": data[:16].hex(), "url": url}
        except Exception as e:
            last = {"ok": False, "error": str(e), "url": url}
    return last

if __name__ == '__main__':
    import ssl, io
    with io.open(sys.argv[1], 'r', encoding='utf-8') as f:
        tasks = json.load(f)
    out = {}
    for key, t in tasks.items():
        res = download(t['url'], t['fn'], t.get('referer'))
        out[key] = res
    print(json.dumps(out, ensure_ascii=False))
