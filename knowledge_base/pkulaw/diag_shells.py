# -*- coding: utf-8 -*-
"""诊断北大法宝管线跑完后，仍缺可chunk实质内容的"空壳"文件。
判据：
  - 有实质附件(attachments/<cli>/ 下有 ok 文件且 bytes>=2KB) → 有内容
  - 或 登录态全文 fulltext_online/<cli>.txt 字符数 >= 300 → 有内容
  - 否则 → 空壳(需补)
"""
import sys, io, os, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
manifest = json.load(open(os.path.join(OUT, "missing_body_manifest.json"), encoding="utf-8"))
prog = json.load(open(os.path.join(OUT, "download_progress.json"), encoding="utf-8"))
ATT = os.path.join(OUT, "attachments")
TXT = os.path.join(OUT, "fulltext_online")

def safe(name):
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()[:120] or "file"

BODY_MIN = 300   # 登录态全文字符阈值
ATT_MIN = 2048   # 附件有效字节阈值

def body_len(cli):
    p = os.path.join(TXT, safe(cli) + ".txt")
    if os.path.exists(p):
        try:
            return len(open(p, encoding="utf-8").read())
        except Exception:
            return 0
    return 0

def att_ok_bytes(cli):
    d = os.path.join(ATT, safe(cli))
    total = 0
    if os.path.isdir(d):
        for f in os.listdir(d):
            fp = os.path.join(d, f)
            if os.path.isfile(fp):
                total += os.path.getsize(fp)
    return total

# 全部 1649 个批量 PDF（用户问的是"压缩包里"缺正文的）
targets = [r for r in manifest if r.get("cli")]

BODY_ORIG_MIN = 200  # 原PDF正文字数阈值
have_pdf = have_att = have_body = shell = 0
shells = []
for r in targets:
    cli = r.get("cli")
    orig = r.get("body_len") or 0
    ab = att_ok_bytes(cli)
    bl = body_len(cli)
    if orig >= BODY_ORIG_MIN:
        have_pdf += 1          # 原PDF自身有正文
    elif ab >= ATT_MIN:
        have_att += 1          # 靠下载的附件
    elif bl >= BODY_MIN:
        have_body += 1         # 靠登录态在线全文
    else:
        shell += 1
        shells.append({
            "cli": cli, "title": (r.get("title") or "")[:45],
            "zip": r.get("zip"), "pages": r.get("pages"),
            "orig_body_len": orig, "has_attachment": r.get("has_attachment"),
            "att_bytes": ab, "online_body": bl,
            "record_url": r.get("record_url"),
            "attach_names": r.get("attachments"),
        })

print(f"批量PDF总数: {len(targets)}")
print(f"  ① 原PDF自身正文>= {BODY_ORIG_MIN}字: {have_pdf}")
print(f"  ② 靠下载附件(>= {ATT_MIN}B): {have_att}")
print(f"  ③ 靠在线全文(>= {BODY_MIN}字): {have_body}")
print(f"  ④ 真空壳(三者皆无): {shell}")

# 空壳再细分：有附件名但没下到 vs 声称有附件 vs 纯短通知
sub_hasatt = [s for s in shells if s["has_attachment"]]
sub_noatt = [s for s in shells if not s["has_attachment"]]
print(f"\n空壳细分: 声称有附件但没下到={len(sub_hasatt)}  无附件的短文={len(sub_noatt)}")
json.dump(shells, open(os.path.join(OUT, "shell_manifest.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(f"空壳清单 -> out/shell_manifest.json")
print("\n--- 声称有附件但没下到的(前15) ---")
for s in sub_hasatt[:15]:
    print(f"  {s['cli']} | {s['title']} | att字节{s['att_bytes']} 在线{s['online_body']} | {s['attach_names']}")
print("\n--- 无附件短文样例(前10) ---")
for s in sub_noatt[:10]:
    print(f"  {s['cli']} | {s['title']} | 原正文{s['orig_body_len']} 在线{s['online_body']}")
