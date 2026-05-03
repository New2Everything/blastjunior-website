#!/usr/bin/env python3
import re
import json
import time
import urllib.request
from pathlib import Path
from html import unescape

OUT_DIR = Path("/root/.openclaw/workspace/learning-v2/reports")
OUT_DIR.mkdir(parents=True, exist_ok=True)

url = "https://blastjunior.com/"

req = urllib.request.Request(
    url,
    headers={"User-Agent": "Mozilla/5.0 (compatible; LearningV2-Audit/1.0)"}
)
html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", errors="ignore")
visible_html = re.sub(r"(?is)<script.*?</script>", " ", html)
visible_html = re.sub(r"(?is)<style.*?</style>", " ", visible_html)

def clean(s: str) -> str:
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = unescape(re.sub(r"\s+", " ", s)).strip()
    return s

title = ""
m = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
if m:
    title = clean(m.group(1))

candidates = []

patterns = [
    ("h1", r"(?is)<h1[^>]*>(.*?)</h1>"),
    ("hero_button", r'(?is)<a[^>]*class="[^"]*(?:btn|button)[^"]*"[^>]*>(.*?)</a>'),
    ("hero_button", r'(?is)<button[^>]*>(.*?)</button>'),
    ("h2", r"(?is)<h2[^>]*>(.*?)</h2>"),
    ("nav_link", r'(?is)<a[^>]*href="[^"]*"[^>]*>(.*?)</a>')
]

for kind, pat in patterns:
    for match in re.finditer(pat, visible_html):
        text = clean(match.group(1))
        if not text:
            continue
        if len(text) > 80:
            continue
        low = text.lower()
        if low in {"skip to content", "menu", "发送", "blastjunior.com", "更多 >"}:
            continue
        if kind == "nav_link":
            if any(x in text for x in ["成员", "积分榜", "画廊", "更多", "blastjunior.com"]):
                continue
        candidates.append({"kind": kind, "text": text})

seen = set()
top = []
for item in candidates:
    key = item["text"]
    if key in seen:
        continue
    seen.add(key)
    top.append(item)
    if len(top) >= 12:
        break

first5 = top[:5]

report = []
report.append("# Homepage First-Screen Audit")
report.append("")
report.append(f"- generated_at: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
report.append(f"- page_title: {title}")
report.append(f"- url: {url}")
report.append("")
report.append("## First 5 likely first-screen elements")
for i, item in enumerate(first5, 1):
    report.append(f"{i}. [{item['kind']}] {item['text']}")
report.append("")
report.append("## Raw top candidates")
for item in top:
    report.append(f"- [{item['kind']}] {item['text']}")

ts = time.strftime("%Y%m%d-%H%M%S", time.localtime())
out = OUT_DIR / f"{ts}-homepage-first-screen-audit.md"
out.write_text("\n".join(report) + "\n")

print(out)
