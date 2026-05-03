#!/usr/bin/env python3
import json
import os
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

HOOK_DIR = WORKSPACE / ".git" / "hooks"
MARKER = "learning-v2-local-git-guard"

REQUIRED_HOOKS = {
    "pre-commit": {
        "must_contain": [
            MARKER,
            "scripts/learning-v2-release-gate.py",
            "scripts/learning-v2-system-only-commit-gate.py",
            "ok_for_commit",
            "git commit blocked",
            "system-only commit allowed by dedicated gate",
            "Push/deploy remain blocked",
        ],
    },
    "pre-push": {
        "must_contain": [
            MARKER,
            "scripts/learning-v2-release-gate.py",
            "ok_for_commit",
            "ok_for_deploy",
            "git push blocked",
            "Cloudflare Pages",
        ],
    },
}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def is_executable(path):
    return path.exists() and os.access(path, os.X_OK)

def audit_hook(name, spec):
    path = HOOK_DIR / name
    result = {
        "name": name,
        "path": str(path),
        "exists": path.exists(),
        "is_file": path.is_file(),
        "is_executable": is_executable(path),
        "missing_tokens": [],
        "ok": False,
    }

    if not path.exists() or not path.is_file():
        result["missing_tokens"] = spec["must_contain"]
        return result

    text = path.read_text(encoding="utf-8", errors="ignore")
    for token in spec["must_contain"]:
        if token not in text:
            result["missing_tokens"].append(token)

    result["ok"] = (
        result["exists"]
        and result["is_file"]
        and result["is_executable"]
        and not result["missing_tokens"]
    )
    return result

def main():
    hook_results = []
    errors = []

    for name, spec in REQUIRED_HOOKS.items():
        r = audit_hook(name, spec)
        hook_results.append(r)
        if not r["ok"]:
            errors.append({
                "hook": name,
                "reason": "hook audit failed",
                "details": r,
            })

    result = "ok" if not errors else "blocked"

    report = {
        "generated_at": now_iso(),
        "auditor": "learning-v2-local-git-guard-auditor",
        "result": result,
        "errors": errors,
        "hooks": hook_results,
        "policy": {
            "pre_commit_required": True,
            "pre_push_required": True,
            "commit_expected_now": "normal blocked; system-only commit allowed only when learning-v2-system-only-commit-gate.py passes",
            "push_expected_now": "blocked",
            "mode": "learning_observe_only",
        },
    }

    out = REPORT_DIR / f"local-git-guard-audit-{stamp()}.json"
    save_json(out, report)

    state = load_json(STATE, default={})
    state["last_local_git_guard_audit"] = {
        "generated_at": report["generated_at"],
        "path": str(out),
        "result": result,
        "errors": errors,
        "hooks": hook_results,
    }
    save_json(STATE, state)

    print("local_git_guard_audit =", result)
    print("audit_report =", out)

    for r in hook_results:
        print(f"{r['name']} exists={r['exists']} executable={r['is_executable']} ok={r['ok']}")
        if r["missing_tokens"]:
            print("  missing_tokens =", ",".join(r["missing_tokens"]))

    if errors:
        raise SystemExit(2)

if __name__ == "__main__":
    main()
