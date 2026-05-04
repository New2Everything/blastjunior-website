#!/usr/bin/env python3
import json
import os
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
HOOK_DIR = WORKSPACE / ".git" / "hooks"
HOOK_DIR.mkdir(parents=True, exist_ok=True)

MARKER = "learning-v2-local-git-guard"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def write_hook(name, content):
    path = HOOK_DIR / name

    if path.exists():
        old = path.read_text(encoding="utf-8", errors="ignore")
        if MARKER not in old:
            backup = HOOK_DIR / f"{name}.backup-{stamp()}"
            backup.write_text(old, encoding="utf-8")
            print(f"backup_existing_hook = {backup}")

    path.write_text(content, encoding="utf-8")
    os.chmod(path, 0o755)
    print(f"installed_hook = {path}")

def main():
    pre_commit = """#!/usr/bin/env bash
# learning-v2-local-git-guard
set -euo pipefail

cd /root/.openclaw/workspace

python3 scripts/learning-v2-release-gate.py >/tmp/learning-v2-pre-commit-gate.log 2>&1 || {
  echo "[learning-v2 guard] release gate returned non-zero. Checking dedicated local commit gates."
  cat /tmp/learning-v2-pre-commit-gate.log
}

python3 - <<'PY'
import json
from pathlib import Path

state = json.loads(Path("learning-v2/state.json").read_text(encoding="utf-8"))
gate_path = state.get("last_release_gate", {}).get("report")
gate = json.loads(Path(gate_path).read_text(encoding="utf-8")) if gate_path else {}
summary = gate.get("summary", {})

errors = []
warnings = []

system_only_ok = False

if summary.get("ok_for_deploy") is True:
    errors.append("unexpected deploy flag during commit")

business_freeze_stable = summary.get("business_freeze_stable") is True

if summary.get("ok_for_commit") is not True:
    # Normal commit remains blocked by release gate. Allow only a staged
    # learning-v2 system-only commit or approved business-only commit
    # if the matching dedicated gate passes.
    import subprocess

    system_gate = subprocess.run(
        ["python3", "scripts/learning-v2-system-only-commit-gate.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    business_gate = subprocess.run(
        ["python3", "scripts/learning-v2-business-only-commit-gate.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if system_gate.returncode == 0:
        system_only_ok = True
        warnings.append("normal release gate blocks commit, but system-only commit gate passed")
        if system_gate.stdout.strip():
            print(system_gate.stdout.strip())
    elif business_gate.returncode == 0:
        system_only_ok = True
        warnings.append("normal release gate blocks commit, but business-only commit gate passed")
        if business_gate.stdout.strip():
            print(business_gate.stdout.strip())
    else:
        errors.append("release gate says ok_for_commit is not True")
        errors.append("neither system-only nor business-only commit gate passed")
        if system_gate.stdout.strip():
            print(system_gate.stdout.strip())
        if system_gate.stderr.strip():
            print(system_gate.stderr.strip())
        if business_gate.stdout.strip():
            print(business_gate.stdout.strip())
        if business_gate.stderr.strip():
            print(business_gate.stderr.strip())

if not business_freeze_stable and not system_only_ok:
    errors.append("business freeze is not stable")

if errors:
    print("[learning-v2 guard] git commit blocked.")
    for e in errors:
        print(" -", e)
    print("Normal commit remains blocked. A local commit requires either system-only or business-only dedicated gate = ok.")
    raise SystemExit(2)

if warnings:
    print("[learning-v2 guard] warnings:")
    for w in warnings:
        print(" -", w)

if system_only_ok:
    print("[learning-v2 guard] dedicated local commit gate passed. Push/deploy remain blocked.")
else:
    print("[learning-v2 guard] commit allowed by release gate.")
PY
"""

    pre_push = """#!/usr/bin/env bash
# learning-v2-local-git-guard
set -euo pipefail

cd /root/.openclaw/workspace

python3 scripts/learning-v2-release-gate.py >/tmp/learning-v2-pre-push-gate.log 2>&1 || {
  echo "[learning-v2 guard] release gate failed. Push blocked."
  cat /tmp/learning-v2-pre-push-gate.log
  exit 2
}

python3 - <<'PY'
import json
from pathlib import Path

state = json.loads(Path("learning-v2/state.json").read_text(encoding="utf-8"))
gate_path = state.get("last_release_gate", {}).get("report")
gate = json.loads(Path(gate_path).read_text(encoding="utf-8")) if gate_path else {}
summary = gate.get("summary", {})

errors = []

if summary.get("ok_for_commit") is not True:
    errors.append("release gate says ok_for_commit is not True")

if summary.get("ok_for_deploy") is not True:
    errors.append("release gate says ok_for_deploy is not True")

if summary.get("business_freeze_stable") is not True:
    errors.append("business freeze is not stable")

if errors:
    print("[learning-v2 guard] git push blocked.")
    for e in errors:
        print(" -", e)
    print("Cloudflare Pages may deploy from GitHub main, so push remains blocked in system_build_only.")
    raise SystemExit(2)

print("[learning-v2 guard] push allowed by release gate.")
PY
"""

    write_hook("pre-commit", pre_commit)
    write_hook("pre-push", pre_push)

    state = {}
    if STATE.exists():
        state = json.loads(STATE.read_text(encoding="utf-8"))

    state["last_local_git_guards"] = {
        "installed_at": now_iso(),
        "hooks": [
            str(HOOK_DIR / "pre-commit"),
            str(HOOK_DIR / "pre-push"),
        ],
        "mode": "system_build_only",
        "expected_behavior_now": {
            "git_commit": "normal blocked; local commit allowed only when system-only or business-only dedicated gate passes",
            "git_push": "blocked",
        },
    }

    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("local_git_guards = installed")
    print("git_commit_expected = normal blocked; system-only or business-only commit allowed only by dedicated gate")
    print("git_push_expected = blocked")

if __name__ == "__main__":
    main()
