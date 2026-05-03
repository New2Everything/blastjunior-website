#!/usr/bin/env python3
import re
import json
import time
import urllib.request
from pathlib import Path
from html import unescape

BASE = Path("/root/.openclaw/workspace/learning-v2")
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

URL = "https://blastjunior.com/"

req = urllib.request.Request(
    URL,
    headers={"User-Agent": "Mozilla/5.0 (compatible; LearningV2-SimplicityAudit/1.0)"}
)
html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", errors="ignore")
visible = re.sub(r"(?is)<script.*?</script>", " ", html)
visible = re.sub(r"(?is)<style.*?</style>", " ", visible)

def clean(s: str) -> str:
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return unescape(re.sub(r"\s+", " ", s)).strip()

# 抓首页主要可见元素
headings = []
for tag in ("h1", "h2", "h3"):
    for m in re.finditer(rf"(?is)<{tag}[^>]*>(.*?)</{tag}>", visible):
        text = clean(m.group(1))
        if text and len(text) <= 80:
            headings.append({"kind": tag, "text": text})

buttons = []
for m in re.finditer(r'(?is)<button[^>]*>(.*?)</button>', visible):
    text = clean(m.group(1))
    if text and len(text) <= 60:
        buttons.append({"kind": "button", "text": text, "href": ""})

links = []
for m in re.finditer(r'(?is)<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', visible):
    href = m.group(1).strip()
    text = clean(m.group(2))
    if text and len(text) <= 60:
        links.append({"kind": "link", "text": text, "href": href})

# 去重，保留前面出现的
def dedupe(items):
    seen = set()
    out = []
    for item in items:
        key = (item.get("kind"), item.get("text"), item.get("href", ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out

headings = dedupe(headings)
buttons = dedupe(buttons)
links = dedupe(links)

# 只保留和首屏复杂度最相关的入口
visible_entries = []

# 主身份/标题
for x in headings:
    if x["kind"] == "h1":
        visible_entries.append({"type": "identity", "text": x["text"], "keep": True, "reason": "品牌/身份识别"})
        break

# 二级区块标题
for x in headings:
    if x["kind"] == "h2":
        visible_entries.append({"type": "section", "text": x["text"], "keep": True, "reason": "首屏核心区块标题"})

# 按钮
for x in buttons:
    txt = x["text"]
    if txt == "发送":
        visible_entries.append({"type": "button", "text": txt, "keep": False, "reason": "聊天发送按钮不是首页主任务入口，可能干扰简洁性"})
    else:
        visible_entries.append({"type": "button", "text": txt, "keep": True, "reason": "显式动作按钮"})

# 导航类链接
for x in links:
    txt = x["text"]
    href = x["href"]
    if txt in {"👥 成员", "📊 积分榜", "📸 画廊"}:
        visible_entries.append({"type": "nav_link", "text": txt, "keep": False, "reason": "信息型导航入口，可能可降权或后置"})
    elif txt in {"🔥 战队"}:
        visible_entries.append({"type": "nav_link", "text": txt, "keep": True, "reason": "当前页面明显展示的主要入口之一"})
    elif txt in {"更多 >", "blastjunior.com"}:
        visible_entries.append({"type": "nav_link", "text": txt, "keep": False, "reason": "次级或页脚入口，不应提升首屏复杂度"})
    else:
        # 其他不收进主要入口统计
        pass

# 再去重
visible_entries = dedupe(visible_entries)

total_entries = len(visible_entries)
demotable = [x for x in visible_entries if not x["keep"]]
keepers = [x for x in visible_entries if x["keep"]]

now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
ts = time.strftime("%Y%m%d-%H%M%S", time.localtime())
out = REPORT_DIR / f"{ts}-simplicity-audit.md"

lines = []
lines.append("# Learning V2 Simplicity Audit")
lines.append("")
lines.append(f"- generated_at: {now}")
lines.append(f"- url: {URL}")
lines.append(f"- visible_entry_count: {total_entries}")
lines.append(f"- keep_count: {len(keepers)}")
lines.append(f"- demotable_count: {len(demotable)}")
lines.append("")
lines.append("## Visible Entries")
for i, x in enumerate(visible_entries, 1):
    status = "KEEP" if x["keep"] else "DEMOTE"
    lines.append(f"{i}. [{status}] {x['type']} :: {x['text']}")
    lines.append(f"   - reason: {x['reason']}")
lines.append("")
lines.append("## Simplification Finding")
if demotable:
    lines.append(f"首屏当前统计到 {total_entries} 个主要暴露入口，其中 {len(demotable)} 个更像可降权/后置对象。简洁性优化应优先减少这些非主任务入口同时暴露。")
else:
    lines.append(f"首屏当前统计到 {total_entries} 个主要暴露入口，暂未发现明显可降权对象。")
lines.append("")
lines.append("## Next Action")
lines.append("- 基于本次统计，选择 1 个可降权对象，提出最小调整方案。")

out.write_text("\n".join(lines) + "\n")

print(out)
print(json.dumps({
    "visible_entry_count": total_entries,
    "keep_count": len(keepers),
    "demotable_count": len(demotable),
    "demotable_texts": [x["text"] for x in demotable],
}, ensure_ascii=False, indent=2))
