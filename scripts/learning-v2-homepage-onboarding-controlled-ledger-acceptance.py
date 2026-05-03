#!/usr/bin/env python3
import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
FREEZE_DIR = BASE / "freezes"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
FREEZE_DIR.mkdir(parents=True, exist_ok=True)

ACCEPTANCE_ID = "learning-v2-homepage-onboarding-controlled-ledger-acceptance-v0"
TARGET_FILE = "public/index.html"

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

def latest_report(pattern):
    reports = sorted(REPORT_DIR.glob(pattern))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def load_release_gate_module():
    path = WORKSPACE / "scripts/learning-v2-release-gate.py"
    spec = importlib.util.spec_from_file_location("learning_v2_release_gate_runtime", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write new dirty freeze and update state.last_dirty_freeze")
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    isolated_path, isolated = latest_report("homepage-onboarding-isolated-post-apply-validator-*.json")
    apply_path, apply_report = latest_report("homepage-onboarding-source-change-apply-apply-*.json")
    post_validator_path, post_validator = latest_report("homepage-onboarding-post-apply-validator-*.json")

    failures = []
    warnings = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_closed:{state.get('allow_source_changes')}")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    if not isolated_path:
        failures.append("missing_isolated_post_apply_validator")

    if isolated.get("result") != "ok":
        failures.append(f"isolated_validator_not_ok:{isolated.get('result')}")

    if isolated.get("isolated_delta_interpretation") != "backup_to_current_delta_is_homepage_onboarding_only":
        failures.append(f"isolated_delta_not_clean:{isolated.get('isolated_delta_interpretation')}")

    if isolated.get("unexpected_removed_line_count") not in (0, None):
        failures.append(f"unexpected_removed_lines:{isolated.get('unexpected_removed_line_count')}")

    if not apply_path:
        failures.append("missing_apply_report")

    if apply_report.get("result") != "ok":
        failures.append(f"apply_report_not_ok:{apply_report.get('result')}")

    if apply_report.get("source_written") is not True:
        failures.append("apply_report_source_written_not_true")

    if apply_report.get("target_file") != TARGET_FILE:
        failures.append(f"apply_target_not_public_index:{apply_report.get('target_file')}")

    backup_path = apply_report.get("backup_path")
    if not backup_path or not Path(backup_path).exists():
        failures.append(f"backup_missing:{backup_path}")

    target_text = (WORKSPACE / TARGET_FILE).read_text(encoding="utf-8", errors="ignore")
    if "home-onboarding" not in target_text:
        failures.append("target_missing_home_onboarding")
    if "home-onboarding-title" not in target_text:
        failures.append("target_missing_home_onboarding_title")

    release_gate = load_release_gate_module()
    entries = release_gate.current_dirty_entries()
    business = [x for x in entries if x.get("class") == "business_source_blocked"]

    freeze_compare = release_gate.compare_business_freeze(state, business)

    changed_paths = sorted([x.get("path") for x in freeze_compare.get("changed", []) if x.get("path")])
    new_business_paths = sorted([x.get("path") for x in freeze_compare.get("new_business_dirty", []) if x.get("path")])
    missing_or_cleaned_paths = sorted([x.get("path") for x in freeze_compare.get("missing_or_cleaned", []) if x.get("path")])

    if changed_paths != [TARGET_FILE]:
        failures.append(f"changed_business_paths_not_exact_target:{changed_paths}")

    if new_business_paths:
        failures.append(f"new_business_dirty_paths_present:{new_business_paths}")

    if missing_or_cleaned_paths:
        failures.append(f"missing_or_cleaned_business_paths_present:{missing_or_cleaned_paths}")

    if not freeze_compare.get("freeze_exists"):
        failures.append("previous_dirty_freeze_missing")

    result = "ok" if not failures else "blocked"

    new_freeze = {
        "generated_at": now_iso(),
        "freeze_type": "controlled_business_source_change_acceptance",
        "acceptance_id": ACCEPTANCE_ID,
        "accepted_target_file": TARGET_FILE,
        "reason": "Accept validated homepage onboarding source change after isolated backup-to-current verification.",
        "previous_dirty_freeze": state.get("last_dirty_freeze"),
        "source_reports": {
            "apply_report": str(apply_path) if apply_path else None,
            "post_apply_validator": str(post_validator_path) if post_validator_path else None,
            "isolated_post_apply_validator": str(isolated_path) if isolated_path else None,
        },
        "freeze_compare_before_acceptance": freeze_compare,
        "business_source_blocked": business,
        "summary": {
            "total_dirty": len(entries),
            "business_source_blocked_count": len(business),
            "system_engineering_allowed_count": len([x for x in entries if x.get("class") == "system_engineering_allowed"]),
            "other_existing_dirty_count": len([x for x in entries if x.get("class") == "other_existing_dirty"]),
            "accepted_changed_business_paths": changed_paths,
            "new_business_dirty_paths": new_business_paths,
            "missing_or_cleaned_business_paths": missing_or_cleaned_paths,
            "commit_allowed": False,
            "push_allowed": False,
            "deploy_allowed": False,
        },
        "policy": {
            "source_written_by_acceptance": False,
            "state_written": bool(args.apply and result == "ok"),
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        }
    }

    out_json = REPORT_DIR / f"homepage-onboarding-controlled-ledger-acceptance-{'apply' if args.apply else 'dry-run'}-{stamp()}.json"
    out_md = REPORT_DIR / f"homepage-onboarding-controlled-ledger-acceptance-{'apply' if args.apply else 'dry-run'}-{stamp()}.md"
    freeze_path = FREEZE_DIR / f"dirty-freeze-controlled-homepage-onboarding-{stamp()}.json"
    ledger_md = SNAPSHOT_DIR / f"homepage-onboarding-controlled-ledger-acceptance-{'apply' if args.apply else 'dry-run'}-{stamp()}.md"

    payload = {
        "generated_at": now_iso(),
        "acceptance_id": ACCEPTANCE_ID,
        "result": result,
        "apply": args.apply,
        "target_file": TARGET_FILE,
        "apply_report": str(apply_path) if apply_path else None,
        "post_apply_validator": str(post_validator_path) if post_validator_path else None,
        "isolated_post_apply_validator": str(isolated_path) if isolated_path else None,
        "previous_dirty_freeze": state.get("last_dirty_freeze"),
        "new_dirty_freeze_path": str(freeze_path) if args.apply and result == "ok" else None,
        "changed_business_paths": changed_paths,
        "new_business_dirty_paths": new_business_paths,
        "missing_or_cleaned_business_paths": missing_or_cleaned_paths,
        "business_source_dirty_count": len(business),
        "ready_to_accept": result == "ok",
        "policy": {
            "source_written_by_acceptance": False,
            "state_written": bool(args.apply and result == "ok"),
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
        "warnings": warnings,
        "failures": failures,
    }

    save_json(out_json, payload)

    lines = []
    lines.append("# Learning V2 Homepage Onboarding Controlled Ledger Acceptance")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- acceptance_id: `{ACCEPTANCE_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- apply: `{str(args.apply).lower()}`")
    lines.append(f"- target_file: `{TARGET_FILE}`")
    lines.append(f"- changed_business_paths: `{changed_paths}`")
    lines.append(f"- new_business_dirty_paths: `{new_business_paths}`")
    lines.append(f"- missing_or_cleaned_business_paths: `{missing_or_cleaned_paths}`")
    lines.append(f"- business_source_dirty_count: `{len(business)}`")
    lines.append(f"- new_dirty_freeze_path: `{payload['new_dirty_freeze_path']}`")
    lines.append("- source_written_by_acceptance: `false`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    if warnings:
        lines.append("")
        lines.append("## Warnings")
        for w in warnings:
            lines.append(f"- {w}")
    if failures:
        lines.append("")
        lines.append("## Failures")
        for f in failures:
            lines.append(f"- {f}")

    md_text = "\n".join(lines)
    out_md.write_text(md_text, encoding="utf-8")
    ledger_md.write_text(md_text, encoding="utf-8")

    if args.apply and result == "ok":
        save_json(freeze_path, new_freeze)

        state["last_dirty_freeze"] = {
            "generated_at": new_freeze["generated_at"],
            "path": str(freeze_path),
            "summary": new_freeze["summary"],
        }

        state["last_controlled_business_change_acceptance"] = {
            "generated_at": payload["generated_at"],
            "acceptance_id": ACCEPTANCE_ID,
            "target_file": TARGET_FILE,
            "acceptance_json": str(out_json),
            "acceptance_md": str(out_md),
            "ledger_md": str(ledger_md),
            "new_dirty_freeze_path": str(freeze_path),
            "source_written_by_acceptance": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        }

        state["allow_source_changes"] = False
        state["allow_git_commit"] = False
        state["allow_deploy"] = False
        pol = state.get("self_evolution_policy")
        if isinstance(pol, dict):
            pol["source_changes_allowed"] = False
            pol["git_commit_allowed"] = False
            pol["git_push_allowed"] = False
            pol["deploy_allowed"] = False

        save_json(STATE, state)

    print("homepage_onboarding_controlled_ledger_acceptance =", result)
    print("acceptance_id =", ACCEPTANCE_ID)
    print("apply =", str(args.apply).lower())
    print("target_file =", TARGET_FILE)
    print("acceptance_json =", out_json)
    print("acceptance_md =", out_md)
    print("ledger_md =", ledger_md)
    print("changed_business_paths =", changed_paths)
    print("new_business_dirty_paths =", new_business_paths)
    print("missing_or_cleaned_business_paths =", missing_or_cleaned_paths)
    print("business_source_dirty_count =", len(business))
    print("ready_to_accept =", str(result == "ok").lower())
    print("new_dirty_freeze_path =", str(freeze_path) if args.apply and result == "ok" else None)
    print("state_written =", str(args.apply and result == "ok").lower())
    print("source_written_by_acceptance = false")
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
