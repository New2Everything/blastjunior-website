#!/usr/bin/env python3
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
FREEZE_DIR = BASE / "freezes"
FREEZE_DIR.mkdir(parents=True, exist_ok=True)

BUSINESS_PREFIXES = (
    "public/",
    "components/",
    "assets/",
    "src/",
    "functions/",
    "workers/",
)

SYSTEM_PREFIXES = (
    "scripts/",
    "learning-v2/",
    ".git/info/exclude",
)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def run(cmd):
    p = subprocess.run(
        cmd,
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return p.returncode, p.stdout, p.stderr

def parse_git_status_z(raw):
    if not raw:
        return []
    parts = raw.split("\0")
    rows = []
    i = 0
    while i < len(parts):
        item = parts[i]
        if not item:
            i += 1
            continue

        code = item[:2]
        path = item[3:] if len(item) > 3 else ""

        if code.strip().startswith(("R", "C")) and i + 1 < len(parts):
            old_path = parts[i + 1]
            rows.append({"code": code, "path": path, "old_path": old_path})
            i += 2
        else:
            rows.append({"code": code, "path": path})
            i += 1
    return rows

def classify(path):
    if path.startswith(BUSINESS_PREFIXES):
        return "business_source_blocked"
    if path.startswith(SYSTEM_PREFIXES):
        return "system_engineering_allowed"
    return "other_existing_dirty"

def file_sha256(path):
    p = WORKSPACE / path
    if not p.exists() or not p.is_file():
        return None
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def head_blob_sha(path):
    rc, out, err = run(["git", "rev-parse", f"HEAD:{path}"])
    if rc != 0:
        return None
    return out.strip()

def main():
    rc, out, err = run(["git", "status", "--porcelain=v1", "-z"])
    if rc != 0:
        print(err)
        raise SystemExit(rc)

    rows = parse_git_status_z(out)
    entries = []

    for row in rows:
        path = row["path"]
        p = WORKSPACE / path
        entries.append({
            **row,
            "class": classify(path),
            "exists_in_worktree": p.exists(),
            "is_file": p.is_file(),
            "worktree_sha256": file_sha256(path),
            "head_blob_sha": head_blob_sha(path),
        })

    business = [x for x in entries if x["class"] == "business_source_blocked"]
    system = [x for x in entries if x["class"] == "system_engineering_allowed"]
    other = [x for x in entries if x["class"] == "other_existing_dirty"]

    freeze = {
        "generated_at": now_iso(),
        "freeze_name": "dirty-freeze-manifest",
        "mode": "system_build_only",
        "purpose": "Record current dirty tree without modifying website source, committing, pushing, or deploying.",
        "summary": {
            "total_dirty": len(entries),
            "business_source_blocked_count": len(business),
            "system_engineering_allowed_count": len(system),
            "other_existing_dirty_count": len(other),
            "commit_allowed": False,
            "push_allowed": False,
            "deploy_allowed": False,
        },
        "policy": {
            "business_source_changes_are_frozen_not_approved": True,
            "system_engineering_may_continue": True,
            "website_source_must_not_be_modified_by_learning_v2_now": True,
        },
        "entries": entries,
        "business_source_blocked": business,
        "system_engineering_allowed": system,
        "other_existing_dirty": other,
    }

    out_path = FREEZE_DIR / f"dirty-freeze-{stamp()}.json"
    out_path.write_text(json.dumps(freeze, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    state = {}
    if STATE.exists():
        state = json.loads(STATE.read_text(encoding="utf-8"))

    state["last_dirty_freeze"] = {
        "generated_at": freeze["generated_at"],
        "path": str(out_path),
        "summary": freeze["summary"],
    }
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("dirty_freeze_manifest =", out_path)
    print("total_dirty =", len(entries))
    print("business_source_blocked_count =", len(business))
    print("system_engineering_allowed_count =", len(system))
    print("other_existing_dirty_count =", len(other))
    print()
    print("business_source_blocked:")
    for x in business:
        print(f"  {x['code']} {x['path']} sha256={x['worktree_sha256']}")
    print()
    print("system_engineering_allowed:")
    for x in system:
        print(f"  {x['code']} {x['path']} sha256={x['worktree_sha256']}")

if __name__ == "__main__":
    main()
