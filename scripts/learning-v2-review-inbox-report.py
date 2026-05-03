#!/usr/bin/env python3
import json
import time
from pathlib import Path

BASE = Path("/root/.openclaw/workspace/learning-v2")
INBOX = BASE / "inbox/directives-inbox.jsonl"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

def classify(raw: str):
    text = raw.strip()
    if any(k in text for k in ["less is more", "用户直接要求", "AI推断不能推翻", "不擅自假设", "先学习设计理念", "多功能堆叠不天然更好"]):
        return "constitution", "更像长期方法论/宪法原则"
    if any(k in text for k in ["blast-api", "blast-homepage-api", "数据库", "数据必须来自数据库", "图库", "画廊", "积分榜", "战队", "选手", "新闻"]):
        return "blxst_directives", "更像 BLXST 项目长期直接要求"
    if any(k in text for k in ["这次先别", "暂时不要", "现在先", "这一轮先", "今天先"]):
        return "temporary", "更像临时任务指令，不建议直接入长期规则"
    return "needs_human_review", "需要人工判断"

lines = [x for x in INBOX.read_text().splitlines() if x.strip()] if INBOX.exists() else []
entries = [json.loads(x) for x in lines]
pending = [e for e in entries if e.get("status") == "pending_review"]

ts = time.strftime("%Y%m%d-%H%M%S", time.localtime())
now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
out = REPORT_DIR / f"{ts}-directives-inbox-review.md"

report = []
report.append("# Directives Inbox Review")
report.append("")
report.append(f"- generated_at: {now}")
report.append(f"- pending_count: {len(pending)}")
report.append("")

for i, e in enumerate(pending, 1):
    target, reason = classify(e.get("raw_text", ""))
    report.append(f"## Item {i}")
    report.append(f"- recorded_at: {e.get('recorded_at','')}")
    report.append(f"- raw_text: {e.get('raw_text','')}")
    report.append(f"- suggested_target: {target}")
    report.append(f"- reason: {reason}")
    report.append("")

out.write_text("\n".join(report) + "\n")
print(out)
