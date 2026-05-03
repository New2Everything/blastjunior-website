#!/usr/bin/env python3
import json
import sys
import time
from pathlib import Path

INBOX = Path("/root/.openclaw/workspace/learning-v2/inbox/directives-inbox.jsonl")
INBOX.parent.mkdir(parents=True, exist_ok=True)

if len(sys.argv) < 2:
    print("Usage: learning-v2-add-directive.py '你的原话要求'")
    sys.exit(1)

raw = " ".join(sys.argv[1:]).strip()
if not raw:
    print("Empty directive")
    sys.exit(1)

entry = {
    "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "source": "user_direct_request",
    "project": "BLXST",
    "raw_text": raw,
    "status": "pending_review",
    "target": None,
    "notes": ""
}

with INBOX.open("a") as f:
    f.write(json.dumps(entry, ensure_ascii=False) + "\n")

print("saved_to =", INBOX)
print(json.dumps(entry, ensure_ascii=False, indent=2))
