#!/usr/bin/env python3
import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
BACKUP_DIR = BASE / "backups"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

TARGET_FILE = WORKSPACE / "public/index.html"
TARGET_REL = "public/index.html"
TARGET_FAMILY = "community.onboarding_experience"
APPLY_ID = "learning-v2-homepage-onboarding-source-change-apply-v0"

ONBOARDING_BLOCK = """
<section class="home-onboarding" aria-labelledby="home-onboarding-title">
  <div class="section-inner">
    <p class="section-kicker">New to HADO?</p>
    <h2 id="home-onboarding-title">Start with one simple path</h2>
    <div class="onboarding-steps" aria-label="HADO starter steps">
      <div class="onboarding-step">
        <strong>1. Understand</strong>
        <span>See how HADO combines sport, teamwork, and AR technology.</span>
      </div>
      <div class="onboarding-step">
        <strong>2. Try</strong>
        <span>Join a beginner-friendly experience with parents, players, or friends.</span>
      </div>
      <div class="onboarding-step">
        <strong>3. Belong</strong>
        <span>Meet the club community, follow events, and find your next match.</span>
      </div>
    </div>
    <p class="onboarding-action">
      <a href="/join.html" class="btn primary">Start here</a>
      <a href="/gallery.html" class="btn secondary">See HADO moments</a>
    </p>
  </div>
</section>
""".strip()

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

def latest_readiness():
    reports = sorted(REPORT_DIR.glob("homepage-onboarding-source-change-gate-readiness-*.json"))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def insert_block(original):
    if "home-onboarding-title" in original or "home-onboarding" in original:
        return original, "already_present"

    insertion = "\n\n" + ONBOARDING_BLOCK + "\n"

    if re.search(r"</main\s*>", original, flags=re.I):
        return re.sub(r"</main\s*>", insertion + "\n</main>", original, count=1, flags=re.I), "before_closing_main"

    if re.search(r"</body\s*>", original, flags=re.I):
        return re.sub(r"</body\s*>", insertion + "\n</body>", original, count=1, flags=re.I), "before_closing_body"

    return original.rstrip() + insertion + "\n", "append_eof"

def close_source_gate(state):
    state["allow_source_changes"] = False
    policy = state.get("self_evolution_policy")
    if isinstance(policy, dict):
        policy["source_changes_allowed"] = False
        policy["git_commit_allowed"] = False
        policy["git_push_allowed"] = False
        policy["deploy_allowed"] = False
    state["allow_git_commit"] = False
    state["allow_deploy"] = False
    return state

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually write public/index.html after all gates pass")
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}
    readiness_path, readiness = latest_readiness()

    failures = []
    warnings = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if integrity.get("result") != "ok":
        failures.append(f"system_integrity_not_ok:{integrity.get('result')}")

    if integrity.get("drift_count") != 0:
        failures.append(f"drift_count_not_zero:{integrity.get('drift_count')}")

    if not readiness_path:
        failures.append("missing_gate_readiness_report")

    if readiness.get("result") != "ok":
        failures.append(f"readiness_not_ok:{readiness.get('result')}")

    if readiness.get("ready_to_open_source_change_gate") is not True:
        failures.append("readiness_does_not_allow_gate_open")

    rec_gate = readiness.get("recommended_gate") or {}
    if rec_gate.get("single_target_file") != TARGET_REL:
        failures.append(f"unexpected_readiness_target:{rec_gate.get('single_target_file')}")

    if rec_gate.get("allow_git_commit") is not False:
        failures.append("readiness_recommends_git_commit")

    if rec_gate.get("allow_deploy") is not False:
        failures.append("readiness_recommends_deploy")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    if not TARGET_FILE.exists():
        failures.append("target_file_missing:public/index.html")

    original = TARGET_FILE.read_text(encoding="utf-8", errors="ignore") if TARGET_FILE.exists() else ""
    proposed, insertion_mode = insert_block(original)

    changed = original != proposed
    already_present = insertion_mode == "already_present"

    if already_present:
        failures.append("home_onboarding_block_already_present")

    if not changed:
        failures.append("no_change_to_apply")

    source_written = False
    backup_path = None
    state_written = False

    if args.apply and not failures:
        # Open the source-change gate only inside this controlled executor.
        state["allow_source_changes"] = True
        policy = state.get("self_evolution_policy")
        if isinstance(policy, dict):
            policy["source_changes_allowed"] = True
            policy["git_commit_allowed"] = False
            policy["git_push_allowed"] = False
            policy["deploy_allowed"] = False
        state["allow_git_commit"] = False
        state["allow_deploy"] = False
        save_json(STATE, state)
        state_written = True

        backup_path = BACKUP_DIR / f"public-index-before-homepage-onboarding-{stamp()}.html"
        shutil.copy2(TARGET_FILE, backup_path)

        TARGET_FILE.write_text(proposed, encoding="utf-8")
        source_written = True

        # Immediately close the gate after the single write.
        state = load_json(STATE, default={})
        state = close_source_gate(state)
        save_json(STATE, state)

    elif not args.apply:
        warnings.append("dry_run_only_no_source_written")

    post_text = TARGET_FILE.read_text(encoding="utf-8", errors="ignore") if TARGET_FILE.exists() else ""

    payload = {
        "generated_at": now_iso(),
        "apply_id": APPLY_ID,
        "result": "ok" if not failures else "blocked",
        "apply": args.apply,
        "target_family": TARGET_FAMILY,
        "target_file": TARGET_REL,
        "readiness_report": str(readiness_path) if readiness_path else None,
        "insertion_mode": insertion_mode,
        "changed": changed,
        "already_present_before_apply": already_present,
        "source_written": source_written,
        "backup_path": str(backup_path) if backup_path else None,
        "post_contains_home_onboarding": "home-onboarding" in post_text,
        "post_contains_home_onboarding_title": "home-onboarding-title" in post_text,
        "policy": {
            "single_target_file": TARGET_REL,
            "state_written": state_written,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "gate_closed_after_apply": True if args.apply and source_written else False
        },
        "warnings": warnings,
        "failures": failures
    }

    suffix = "apply" if args.apply else "dry-run"
    out_json = REPORT_DIR / f"homepage-onboarding-source-change-apply-{suffix}-{stamp()}.json"
    out_md = REPORT_DIR / f"homepage-onboarding-source-change-apply-{suffix}-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Homepage Onboarding Source Change Apply")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- apply_id: `{APPLY_ID}`")
    lines.append(f"- result: `{payload['result']}`")
    lines.append(f"- apply: `{str(args.apply).lower()}`")
    lines.append(f"- target_file: `{TARGET_REL}`")
    lines.append(f"- source_written: `{str(source_written).lower()}`")
    lines.append(f"- backup_path: `{payload['backup_path']}`")
    lines.append(f"- git_commit: `false`")
    lines.append(f"- git_push: `false`")
    lines.append(f"- deploy: `false`")
    lines.append("")
    if warnings:
        lines.append("## Warnings")
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")
    if failures:
        lines.append("## Failures")
        for f in failures:
            lines.append(f"- {f}")
        lines.append("")
    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("homepage_onboarding_source_change_apply =", payload["result"])
    print("apply_id =", APPLY_ID)
    print("apply =", str(args.apply).lower())
    print("target_file =", TARGET_REL)
    print("readiness_report =", readiness_path)
    print("report_json =", out_json)
    print("report_md =", out_md)
    print("insertion_mode =", insertion_mode)
    print("changed =", str(changed).lower())
    print("source_written =", str(source_written).lower())
    print("backup_path =", backup_path)
    print("post_contains_home_onboarding =", str(payload["post_contains_home_onboarding"]).lower())
    print("post_contains_home_onboarding_title =", str(payload["post_contains_home_onboarding_title"]).lower())
    print("state_written =", str(state_written).lower())
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if warnings:
        print()
        print("warnings:")
        for w in warnings:
            print(" ", w)

    if failures:
        print()
        print("failures:")
        for f in failures:
            print(" ", f)
        raise SystemExit(2)

if __name__ == "__main__":
    main()
