#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

PLANNER_ID = "learning-v2-opportunity-controlled-change-plan-v0.1"
REGISTRY_PATH = BASE / "target-family-registry.json"

PLANNED_CSS = '''/* learning-v2 repair: missing asset reference
   Purpose: satisfy /assets/css/site.css?v=20260110 for Cloudflare Pages public root.
   This file intentionally imports the existing site stylesheet instead of redesigning pages.
*/

@import url("/styles.css");
'''

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def load_target_family_registry():
    registry = load_json(REGISTRY_PATH, default={}) or {}
    families = registry.get("families") or {}
    return registry, families


def latest_validation_gate():
    files = sorted(
        REPORT_DIR.glob("opportunity-validation-gate-*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files[0] if files else None

def main():
    gate_path = latest_validation_gate()
    if not gate_path:
        raise SystemExit("NO_VALIDATION_GATE_REPORT_FOUND")

    gate = load_json(gate_path, default={}) or {}

    failures = []
    warnings = []

    target_family = gate.get("target_family")
    files_to_change = gate.get("files_to_change") or []

    registry, registry_families = load_target_family_registry()
    registry_family = registry_families.get(target_family) or {}
    registry_warnings = []

    if target_family and not registry_family:
        registry_warnings.append(f"target_family_not_in_registry:{target_family}")

    if registry_family and registry_family.get("status") != "supported":
        registry_warnings.append(f"registry_family_not_supported:{target_family}:{registry_family.get('status')}")

    if registry_family and registry_family.get("plan_mode") is None:
        registry_warnings.append(f"registry_plan_mode_missing:{target_family}")

    warnings.extend(registry_warnings)

    if gate.get("result") != "ok":
        failures.append(f"validation_gate_not_ok:{gate.get('result')}")

    if target_family == "event.storytelling_path":
        if files_to_change:
            failures.append(f"event_storytelling_proposal_only_requires_no_files:{files_to_change}")

        result = "ok" if not failures else "blocked"

        plan = {
            "plan_id": "controlled-change-plan-event-storytelling-path-proposal-only-v0",
            "change_type": "proposal_only_no_source_change",
            "target_file": None,
            "planned_content": "",
            "reason": "Support event.storytelling_path as a design capability lifecycle target without editing website files yet.",
            "source_reference": gate.get("source_proposal_report"),
            "strategy": "Record a proposal-only controlled plan. Do not choose final page placement, do not apply, and do not edit public/components/worker/sql files.",
            "expected_validation": [
                "validation gate result is ok",
                "files_to_change remains empty",
                "website_files_changed remains false",
                "system_integrity remains ok",
                "later implementation requires a separate controlled source-change plan"
            ],
            "non_goals": [
                "do not edit public files",
                "do not edit components",
                "do not generate final marketing copy",
                "do not apply website changes",
                "do not push",
                "do not deploy"
            ],
        }

        recommended_next_stage = "design_review_or_implementation_readiness" if result == "ok" else "plan_revision"

    elif target_family == "quality.missing_asset_reference":
        if files_to_change != ["public/assets/css/site.css"]:
            failures.append(f"unexpected_files_to_change:{files_to_change}")

        target = WORKSPACE / "public/assets/css/site.css"
        if target.exists():
            warnings.append("target_file_already_exists")

        source_styles = WORKSPACE / "public/styles.css"
        if not source_styles.exists():
            failures.append("source_styles_css_missing:public/styles.css")

        result = "ok" if not failures else "blocked"

        plan = {
            "plan_id": "controlled-change-plan-create-public-assets-css-site-css-v0",
            "change_type": "create_file",
            "target_file": "public/assets/css/site.css",
            "planned_content": PLANNED_CSS,
            "reason": "Repair missing stylesheet asset referenced by public/about.html.",
            "source_reference": "public/about.html href=/assets/css/site.css?v=20260110",
            "strategy": "Create a small bridge stylesheet that imports existing /styles.css; do not redesign the page.",
            "expected_validation": [
                "public/assets/css/site.css exists after apply",
                "design-opportunity-discoverer no longer reports this missing asset",
                "system_integrity remains ok",
            ],
            "non_goals": [
                "do not redesign public/about.html",
                "do not edit public/about.html",
                "do not edit gallery.html or news.html",
                "do not push",
                "do not deploy",
            ],
        }

        recommended_next_stage = "controlled_apply" if result == "ok" else "plan_revision"

    else:
        failures.append(f"unsupported_target_family:{target_family}")
        result = "blocked"
        plan = {
            "plan_id": f"controlled-change-plan-unsupported-{target_family}-v0",
            "change_type": "unsupported",
            "target_file": None,
            "planned_content": "",
            "reason": "Target family is not supported by this planner yet.",
            "source_reference": gate.get("source_proposal_report"),
            "strategy": "Add target-specific controlled-change-plan support before proceeding.",
            "expected_validation": [],
            "non_goals": [
                "do not apply",
                "do not push",
                "do not deploy",
            ],
        }
        recommended_next_stage = "plan_revision"

    payload = {
        "generated_at": now_iso(),
        "planner_id": PLANNER_ID,
        "result": result,
        "source_validation_gate": str(gate_path),
        "target_family": gate.get("target_family"),
        "registry_family_status": registry_family.get("status"),
        "registry_current_support": registry_family.get("current_support"),
        "registry_type": registry_family.get("type"),
        "registry_lane": registry_family.get("lane"),
        "registry_plan_mode": registry_family.get("plan_mode"),
        "registry_path": str(REGISTRY_PATH),
        "registry_warnings": registry_warnings,
        "proposal_id": gate.get("proposal_id"),
        "files_to_change": files_to_change,
        "plan": plan,
        "failures": failures,
        "warnings": warnings,
        "policy": {
            "dry_run_only": True,
            "website_files_changed": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "restore_cloudflare_auto_deploy": False,
        },
        "recommended_next_stage": recommended_next_stage,
    }

    out_json = REPORT_DIR / f"opportunity-controlled-change-plan-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"opportunity-controlled-change-plan-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Opportunity Controlled Change Plan",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- planner_id: `{PLANNER_ID}`",
        f"- result: `{result}`",
        f"- source_validation_gate: `{payload['source_validation_gate']}`",
        f"- target_family: `{payload['target_family']}`",
        f"- registry_family_status: `{registry_family.get('status')}`",
        f"- registry_current_support: `{registry_family.get('current_support')}`",
        f"- registry_type: `{registry_family.get('type')}`",
        f"- registry_lane: `{registry_family.get('lane')}`",
        f"- registry_plan_mode: `{registry_family.get('plan_mode')}`",
        f"- proposal_id: `{payload['proposal_id']}`",
        f"- recommended_next_stage: `{payload['recommended_next_stage']}`",
        "",
        "## Planned Change",
        "",
        f"- change_type: `{plan['change_type']}`",
        f"- target_file: `{plan['target_file']}`",
        f"- strategy: {plan['strategy']}",
        "",
        "## Planned Content",
        "",
        "```css",
        (plan.get("planned_content") or "").rstrip(),
        "```",
        "",
        "## Expected Validation",
        "",
    ]

    for item in plan["expected_validation"]:
        lines.append(f"- {item}")

    lines += [
        "",
        "## Failures",
        "",
    ]
    lines += [f"- {f}" for f in failures] if failures else ["- none"]

    lines += [
        "",
        "## Warnings",
        "",
    ]
    lines += [f"- {w}" for w in warnings] if warnings else ["- none"]

    lines += [
        "",
        "## Safety",
        "",
        "- website_files_changed: `false`",
        "- git_commit: `false`",
        "- git_push: `false`",
        "- deploy: `false`",
        "- restore_cloudflare_auto_deploy: `false`",
        "",
    ]

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("opportunity_controlled_change_plan =", result)
    print("target_family =", target_family)
    print("registry_family_status =", registry_family.get("status"))
    print("registry_current_support =", registry_family.get("current_support"))
    print("registry_type =", registry_family.get("type"))
    print("registry_lane =", registry_family.get("lane"))
    print("registry_plan_mode =", registry_family.get("plan_mode"))
    print("target_file =", plan["target_file"])
    print("change_type =", plan["change_type"])
    print("recommended_next_stage =", payload["recommended_next_stage"])
    print("report_json =", out_json)
    print("report_md =", out_md)
    if failures:
        print("failures =", json.dumps(failures, ensure_ascii=False, indent=2))
    if warnings:
        print("warnings =", json.dumps(warnings, ensure_ascii=False, indent=2))
    print("website_files_changed = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

if __name__ == "__main__":
    main()
