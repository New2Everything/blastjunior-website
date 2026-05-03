#!/usr/bin/env python3
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
MODE_POLICY = BASE / "mode-policy.json"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

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
    return {
        "cmd": cmd,
        "returncode": p.returncode,
        "stdout": p.stdout.strip(),
        "stderr": p.stderr.strip(),
    }

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def find_key(obj, key):
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                found.append(v)
            found.extend(find_key(v, key))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(find_key(item, key))
    return found

def last_value(state, key, default=None):
    values = find_key(state, key)
    if not values:
        return default
    return values[-1]

def current_mode(state, policy):
    known_modes = set((policy.get("modes") or {}).keys())

    sep = state.get("self_evolution_policy") or {}
    if isinstance(sep, dict) and sep.get("mode") in known_modes:
        return sep.get("mode")

    mp = state.get("mode_policy")
    if isinstance(mp, dict) and mp.get("mode") in known_modes:
        return mp.get("mode")
    if isinstance(mp, str) and mp in known_modes:
        return mp

    audit = state.get("last_mode_policy_audit") or {}
    if audit.get("current_mode") in known_modes:
        return audit.get("current_mode")

    if state.get("system_build_only") is True:
        return "system_build_only"

    return None

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

def current_dirty_entries():
    git_status = run(["git", "status", "--porcelain=v1", "-z"])
    if git_status["returncode"] != 0:
        raise RuntimeError(git_status["stderr"] or "git status failed")

    rows = parse_git_status_z(git_status["stdout"])
    entries = []
    for row in rows:
        path = row.get("path", "")
        p = WORKSPACE / path
        entries.append({
            **row,
            "class": classify(path),
            "exists_in_worktree": p.exists(),
            "is_file": p.is_file(),
            "worktree_sha256": file_sha256(path),
        })
    return entries

def compare_business_freeze(state, current_business):
    freeze_info = state.get("last_dirty_freeze") or {}
    freeze_path = freeze_info.get("path")

    result = {
        "freeze_path": freeze_path,
        "freeze_exists": False,
        "stable": False,
        "changed": [],
        "missing_or_cleaned": [],
        "new_business_dirty": [],
        "frozen_count": 0,
        "current_count": len(current_business),
    }

    if not freeze_path:
        result["reason"] = "no last_dirty_freeze path in state"
        return result

    freeze = load_json(freeze_path)
    if not freeze:
        result["reason"] = "freeze file not found or unreadable"
        return result

    result["freeze_exists"] = True

    frozen_business = freeze.get("business_source_blocked", [])
    result["frozen_count"] = len(frozen_business)

    frozen_by_path = {x.get("path"): x for x in frozen_business if x.get("path")}
    current_by_path = {x.get("path"): x for x in current_business if x.get("path")}

    for path, old in frozen_by_path.items():
        cur = current_by_path.get(path)
        if not cur:
            result["missing_or_cleaned"].append({
                "path": path,
                "old_code": old.get("code"),
                "old_sha256": old.get("worktree_sha256"),
            })
            continue

        if cur.get("code") != old.get("code") or cur.get("worktree_sha256") != old.get("worktree_sha256"):
            result["changed"].append({
                "path": path,
                "old_code": old.get("code"),
                "new_code": cur.get("code"),
                "old_sha256": old.get("worktree_sha256"),
                "new_sha256": cur.get("worktree_sha256"),
            })

    for path, cur in current_by_path.items():
        if path not in frozen_by_path:
            result["new_business_dirty"].append({
                "path": path,
                "code": cur.get("code"),
                "sha256": cur.get("worktree_sha256"),
            })

    result["stable"] = (
        not result["changed"]
        and not result["missing_or_cleaned"]
        and not result["new_business_dirty"]
    )

    return result

def main():
    state = load_json(STATE, default={})
    policy = load_json(MODE_POLICY, default={})
    mode = current_mode(state, policy)
    mode_rule = (policy.get("modes") or {}).get(mode) or {}

    all_safe = run(["python3", "scripts/learning-v2-control.py", "all-safe"])

    entries = current_dirty_entries()

    business = [x for x in entries if x["class"] == "business_source_blocked"]
    system = [x for x in entries if x["class"] == "system_engineering_allowed"]
    other = [x for x in entries if x["class"] == "other_existing_dirty"]

    freeze_compare = compare_business_freeze(state, business)

    current_topic = state.get("current_topic")
    current_stage = state.get("current_stage")

    def policy_value(key):
        if key in state:
            return state.get(key)
        return last_value(state, key)

    allow_source_changes = policy_value("allow_source_changes")
    allow_git_commit = policy_value("allow_git_commit")
    allow_deploy = policy_value("allow_deploy")
    doctor_result = last_value(state, "doctor_result")

    active_cycle_must_be_paused = mode_rule.get("active_cycle_must_be_paused") is True
    active_cycle_is_paused = current_topic in (None, "", "None") and current_stage in (None, "", "None")

    checks = [
        {
            "name": "current_mode_known",
            "ok": mode in (policy.get("modes") or {}),
            "details": {
                "current_mode": mode,
                "known_modes": sorted((policy.get("modes") or {}).keys()),
            },
        },
        {
            "name": "active_cycle_policy_ok",
            "ok": active_cycle_is_paused if active_cycle_must_be_paused else True,
            "details": {
                "current_mode": mode,
                "active_cycle_must_be_paused": active_cycle_must_be_paused,
                "active_cycle_is_paused": active_cycle_is_paused,
                "current_topic": current_topic,
                "current_stage": current_stage,
            },
        },
        {
            "name": "source_changes_disabled",
            "ok": allow_source_changes is False,
            "details": {"allow_source_changes": allow_source_changes},
        },
        {
            "name": "git_commit_disabled",
            "ok": allow_git_commit is False,
            "details": {"allow_git_commit": allow_git_commit},
        },
        {
            "name": "deploy_disabled",
            "ok": allow_deploy is False,
            "details": {"allow_deploy": allow_deploy},
        },
        {
            "name": "mode_rule_source_changes_blocked",
            "ok": mode_rule.get("source_changes_allowed") is False,
            "details": {"source_changes_allowed": mode_rule.get("source_changes_allowed")},
        },
        {
            "name": "mode_rule_git_commit_blocked",
            "ok": mode_rule.get("git_commit_allowed") is False,
            "details": {"git_commit_allowed": mode_rule.get("git_commit_allowed")},
        },
        {
            "name": "mode_rule_git_push_blocked",
            "ok": mode_rule.get("git_push_allowed") is False,
            "details": {"git_push_allowed": mode_rule.get("git_push_allowed")},
        },
        {
            "name": "mode_rule_deploy_blocked",
            "ok": mode_rule.get("deploy_allowed") is False,
            "details": {"deploy_allowed": mode_rule.get("deploy_allowed")},
        },
        {
            "name": "control_all_safe_ok",
            "ok": all_safe["returncode"] == 0,
            "details": {
                "returncode": all_safe["returncode"],
                "stdout_tail": all_safe["stdout"][-1200:],
                "stderr_tail": all_safe["stderr"][-1200:],
                "doctor_result_before_gate": doctor_result,
            },
        },
        {
            "name": "business_source_matches_dirty_freeze",
            "ok": freeze_compare["freeze_exists"] and freeze_compare["stable"],
            "details": freeze_compare,
        },
    ]

    ok_for_system_build = all(c["ok"] for c in checks)
    ok_for_commit = False
    ok_for_deploy = False

    hard_blocks = []

    if business:
        hard_blocks.append("business_source_dirty_exists")
    if not freeze_compare["freeze_exists"]:
        hard_blocks.append("dirty_freeze_missing")
    elif not freeze_compare["stable"]:
        hard_blocks.append("business_source_dirty_changed_since_freeze")
    if allow_git_commit is not False:
        hard_blocks.append("allow_git_commit_not_false")
    if allow_deploy is not False:
        hard_blocks.append("allow_deploy_not_false")

    report = {
        "generated_at": now_iso(),
        "gate_name": "learning-v2-release-gate",
        "mode": mode,
        "mode_policy_version": policy.get("version"),
        "summary": {
            "ok_for_system_build": ok_for_system_build,
            "ok_for_commit": ok_for_commit,
            "ok_for_deploy": ok_for_deploy,
            "hard_blocks": hard_blocks,
            "business_source_dirty_count": len(business),
            "system_engineering_dirty_count": len(system),
            "other_dirty_count": len(other),
            "business_freeze_stable": freeze_compare["stable"],
        },
        "checks": checks,
        "git": {
            "classified_dirty": entries,
            "business_source_dirty": business,
            "system_engineering_dirty": system,
            "other_dirty": other,
        },
        "freeze_compare": freeze_compare,
        "policy": {
            "no_website_source_changes": True,
            "no_commit": True,
            "no_push": True,
            "no_deploy": True,
            "business_source_dirty_must_match_freeze": True,
            "release_commit_requires_explicit_future_manual_unlock": True,
            "mode_aware_active_cycle_policy": True,
        },
    }

    out = REPORT_DIR / f"release-gate-{stamp()}.json"
    save_json(out, report)

    state["last_release_gate"] = {
        "generated_at": report["generated_at"],
        "report": str(out),
        "summary": report["summary"],
        "mode": mode,
        "mode_policy_version": policy.get("version"),
    }
    save_json(STATE, state)

    print("release_gate_report =", out)
    print("mode =", mode)
    print("mode_policy_version =", policy.get("version"))
    print("ok_for_system_build =", ok_for_system_build)
    print("ok_for_commit =", ok_for_commit)
    print("ok_for_deploy =", ok_for_deploy)
    print("business_freeze_stable =", freeze_compare["stable"])
    print("hard_blocks =", ",".join(hard_blocks) if hard_blocks else "none")
    print("business_source_dirty_count =", len(business))
    print("system_engineering_dirty_count =", len(system))
    print("other_dirty_count =", len(other))

    if freeze_compare.get("changed"):
        print()
        print("changed_business_source:")
        for x in freeze_compare["changed"]:
            print(" ", x["path"])

    if freeze_compare.get("missing_or_cleaned"):
        print()
        print("missing_or_cleaned_business_source:")
        for x in freeze_compare["missing_or_cleaned"]:
            print(" ", x["path"])

    if freeze_compare.get("new_business_dirty"):
        print()
        print("new_business_dirty:")
        for x in freeze_compare["new_business_dirty"]:
            print(" ", x["path"])

    if not ok_for_system_build:
        raise SystemExit(2)

if __name__ == "__main__":
    main()
