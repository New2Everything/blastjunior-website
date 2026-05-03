#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_FAMILY = "simplicity.dead_or_duplicate_entry_scan"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def latest_probe_report():
    reports = sorted(REPORT_DIR.glob("dead-duplicate-entry-probe-*.json"))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}
    probe_path, probe = latest_probe_report()

    failures = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_false:{state.get('allow_source_changes')}")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    if integrity.get("result") != "ok":
        failures.append(f"system_integrity_not_ok:{integrity.get('result')}")

    if not probe_path:
        failures.append("missing_dead_duplicate_probe_report")

    if TARGET_FAMILY in set(state.get("disabled_target_families") or []):
        failures.append(f"target_family_already_disabled:{TARGET_FAMILY}")

    result = "ok" if not failures else "blocked"

    recommended_changes = [
        {
            "file": "scripts/learning-v2-topic-selector.py",
            "change": "make selector target-family aware for simplicity.dead_or_duplicate_entry_scan",
            "dry_run_first": True,
            "state_effect_if_apply_later": {
                "current_topic": "simplicity",
                "current_stage": "dead_duplicate_probe",
                "current_target_family": TARGET_FAMILY,
            },
            "source_write_risk": False,
        },
        {
            "file": "scripts/learning-v2-dispatch.py",
            "change": "add branch for topic=simplicity, stage=dead_duplicate_probe, target_family=simplicity.dead_or_duplicate_entry_scan",
            "dry_run_first": True,
            "child_script": "scripts/learning-v2-dead-duplicate-entry-probe.py",
            "source_write_risk": False,
        },
        {
            "file": "scripts/learning-v2-dead-duplicate-entry-probe.py",
            "change": "keep as probe-only; do not create apply executor yet",
            "dry_run_first": True,
            "source_write_risk": False,
        },
    ]

    report = {
        "generated_at": now_iso(),
        "design": "learning-v2-dead-duplicate-family-design",
        "target_family": TARGET_FAMILY,
        "result": result,
        "failures": failures,
        "current_state": {
            "current_topic": state.get("current_topic"),
            "current_stage": state.get("current_stage"),
            "current_target_family": state.get("current_target_family"),
            "disabled_target_families": state.get("disabled_target_families") or [],
            "allow_source_changes": state.get("allow_source_changes"),
            "allow_git_commit": state.get("allow_git_commit"),
            "allow_deploy": state.get("allow_deploy"),
            "system_integrity": integrity.get("result"),
        },
        "latest_probe": {
            "path": str(probe_path) if probe_path else None,
            "records_count": probe.get("records_count"),
            "duplicate_label_count": len(probe.get("duplicate_labels") or {}),
            "auto_applied_comment_count": len(probe.get("auto_applied_comments") or []),
            "weak_candidate_count": len(probe.get("weak_candidates") or []),
        },
        "recommended_changes": recommended_changes,
        "guardrails": {
            "do_not_modify_website_source": True,
            "do_not_commit": True,
            "do_not_push": True,
            "do_not_deploy": True,
            "selector_must_set_current_target_family": True,
            "dispatch_must_check_current_target_family": True,
            "probe_only_before_any_apply_executor": True,
        },
        "policy": {
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "design_only": True,
        },
    }

    out_json = REPORT_DIR / f"dead-duplicate-family-design-{stamp()}.json"
    out_md = REPORT_DIR / f"dead-duplicate-family-design-{stamp()}.md"

    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Dead / Duplicate Entry Target-Family Design")
    lines.append("")
    lines.append(f"- generated_at: `{report['generated_at']}`")
    lines.append(f"- target_family: `{TARGET_FAMILY}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- latest_probe: `{report['latest_probe']['path']}`")
    lines.append("- source_changed: `false`")
    lines.append("- state_written: `false`")
    lines.append("")
    lines.append("## Why this cannot reuse the old simplicity discover path")
    lines.append("")
    lines.append("The old `simplicity/discover` path routes completed section-more work into nav discovery. This new target-family must not accidentally enter `simplicity.nav_anchor_deprioritize`.")
    lines.append("")
    lines.append("## Required integration shape")
    lines.append("")
    lines.append("```text")
    lines.append("selector -> current_topic=simplicity")
    lines.append("selector -> current_stage=dead_duplicate_probe")
    lines.append(f"selector -> current_target_family={TARGET_FAMILY}")
    lines.append("dispatch -> run dead_duplicate_entry_probe only")
    lines.append("```")
    lines.append("")
    lines.append("## Recommended changes")
    lines.append("")
    for item in recommended_changes:
        lines.append(f"### `{item['file']}`")
        lines.append("")
        lines.append(f"- change: {item['change']}")
        lines.append(f"- dry_run_first: `{str(item['dry_run_first']).lower()}`")
        lines.append(f"- source_write_risk: `{str(item['source_write_risk']).lower()}`")
        lines.append("")
    lines.append("## Guardrails")
    lines.append("")
    for k, v in report["guardrails"].items():
        lines.append(f"- `{k}` = `{str(v).lower()}`")
    lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("dead_duplicate_family_design =", result)
    print("target_family =", TARGET_FAMILY)
    print("design_json =", out_json)
    print("design_md =", out_md)
    print("latest_probe =", probe_path)
    print("recommended_selector_stage = dead_duplicate_probe")
    print("recommended_current_target_family =", TARGET_FAMILY)
    print("state_written = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if failures:
        print()
        print("failures:")
        for x in failures:
            print(" ", x)
        raise SystemExit(2)

if __name__ == "__main__":
    main()
