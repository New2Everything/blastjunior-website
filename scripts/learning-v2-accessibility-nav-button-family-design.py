#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_FAMILY = "accessibility.navigation_button_semantics"

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
    reports = sorted(REPORT_DIR.glob("accessibility-nav-button-semantics-probe-*.json"))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def latest_activation_design():
    reports = sorted(REPORT_DIR.glob("research-candidate-activation-design-*.json"))
    if not reports:
        return None, {}
    p = reports[-1]
    return p, load_json(p, default={})

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}
    probe_path, probe = latest_probe_report()
    activation_path, activation = latest_activation_design()

    failures = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if state.get("current_topic") is not None:
        failures.append(f"current_topic_not_idle:{state.get('current_topic')}")

    if state.get("current_stage") is not None:
        failures.append(f"current_stage_not_idle:{state.get('current_stage')}")

    if state.get("current_target_family") is not None:
        failures.append(f"current_target_family_not_idle:{state.get('current_target_family')}")

    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_false:{state.get('allow_source_changes')}")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    if integrity.get("result") != "ok":
        failures.append(f"system_integrity_not_ok:{integrity.get('result')}")

    if not probe_path:
        failures.append("missing_nav_button_semantics_probe_report")

    if probe.get("target_family") != TARGET_FAMILY:
        failures.append(f"probe_target_family_mismatch:{probe.get('target_family')}")

    if TARGET_FAMILY in set(state.get("disabled_target_families") or []):
        failures.append(f"target_family_already_disabled:{TARGET_FAMILY}")

    summary = probe.get("summary") or {}
    findings = probe.get("findings") or []
    review_items = [x for x in findings if x.get("severity") == "review"]

    result = "ok" if not failures else "blocked"

    report = {
        "generated_at": now_iso(),
        "design": "learning-v2-accessibility-nav-button-family-design",
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
            "drift_count": integrity.get("drift_count"),
        },
        "research_origin": {
            "activation_design": str(activation_path) if activation_path else None,
            "candidate_target_family": TARGET_FAMILY,
            "candidate_source": "research-test-chain",
        },
        "latest_probe": {
            "path": str(probe_path) if probe_path else None,
            "total_findings": summary.get("total_findings"),
            "ok_count": summary.get("ok_count"),
            "review_count": summary.get("review_count"),
            "warning_count": summary.get("warning_count"),
            "missing_field_count": summary.get("missing_field_count"),
            "review_preview": review_items[:8],
        },
        "recommended_integration": {
            "topic": "accessibility-basics",
            "stage": "accessibility_nav_button_probe",
            "current_target_family": TARGET_FAMILY,
            "probe_script": "scripts/learning-v2-accessibility-nav-button-semantics-probe.py",
            "dispatch_executor": "accessibility_nav_button_semantics_probe",
            "selector_route_allowed_only_after_dry_run": True,
            "dispatch_route_must_check_target_family": True,
        },
        "future_chain": [
            "selector dry-run route",
            "dispatch dry-run route",
            "dispatch sandbox verification",
            "selector apply only when idle",
            "dispatch apply probe only",
            "probe resolver to accessibility_nav_button_review_ready",
            "review executor to accessibility_nav_button_proposal_ready",
            "proposal finalizer to track_complete",
            "track-complete finalizer to idle and disabled",
        ],
        "guardrails": {
            "do_not_modify_website_source": True,
            "do_not_commit": True,
            "do_not_push": True,
            "do_not_deploy": True,
            "new_target_family_must_probe_before_review": True,
            "new_target_family_must_have_dispatch_dry_run_before_apply": True,
            "source_change_allowed_required_before_any_website_edit": True,
            "research_candidate_does_not_grant_source_change_permission": True,
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

    out_json = REPORT_DIR / f"accessibility-nav-button-family-design-{stamp()}.json"
    out_md = REPORT_DIR / f"accessibility-nav-button-family-design-{stamp()}.md"

    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Accessibility Navigation Button Semantics Target-Family Design")
    lines.append("")
    lines.append(f"- generated_at: `{report['generated_at']}`")
    lines.append(f"- target_family: `{TARGET_FAMILY}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- latest_probe: `{report['latest_probe']['path']}`")
    lines.append(f"- total_findings: `{report['latest_probe']['total_findings']}`")
    lines.append(f"- review_count: `{report['latest_probe']['review_count']}`")
    lines.append(f"- missing_field_count: `{report['latest_probe']['missing_field_count']}`")
    lines.append("- source_changed: `false`")
    lines.append("- state_written: `false`")
    lines.append("")
    lines.append("## Research origin")
    lines.append("")
    lines.append(f"- activation_design: `{report['research_origin']['activation_design']}`")
    lines.append(f"- candidate_source: `{report['research_origin']['candidate_source']}`")
    lines.append("")
    lines.append("## Required integration shape")
    lines.append("")
    lines.append("```text")
    lines.append("selector -> current_topic=accessibility-basics")
    lines.append("selector -> current_stage=accessibility_nav_button_probe")
    lines.append(f"selector -> current_target_family={TARGET_FAMILY}")
    lines.append("dispatch -> run accessibility_nav_button_semantics_probe only")
    lines.append("```")
    lines.append("")
    lines.append("## Review findings preview")
    lines.append("")
    if review_items:
        for item in review_items[:8]:
            missing = ", ".join(item.get("missing") or [])
            lines.append(f"- `{item.get('file')}:{item.get('line')}` `{item.get('kind')}` missing `{missing}` — {item.get('recommendation')}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Future chain")
    lines.append("")
    for item in report["future_chain"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Guardrails")
    lines.append("")
    for k, v in report["guardrails"].items():
        lines.append(f"- `{k}` = `{str(v).lower()}`")
    lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("accessibility_nav_button_family_design =", result)
    print("target_family =", TARGET_FAMILY)
    print("design_json =", out_json)
    print("design_md =", out_md)
    print("latest_probe =", probe_path)
    print("recommended_topic = accessibility-basics")
    print("recommended_selector_stage = accessibility_nav_button_probe")
    print("recommended_current_target_family =", TARGET_FAMILY)
    print("review_count =", summary.get("review_count"))
    print("missing_field_count =", summary.get("missing_field_count"))
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
