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

PLANNER_ID = "learning-v2-opportunity-controlled-change-plan-v0"

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

    if gate.get("result") != "ok":
        failures.append(f"validation_gate_not_ok:{gate.get('result')}")

    files_to_change = gate.get("files_to_change") or []
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

    payload = {
        "generated_at": now_iso(),
        "planner_id": PLANNER_ID,
        "result": result,
        "source_validation_gate": str(gate_path),
        "target_family": gate.get("target_family"),
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
        "recommended_next_stage": "controlled_apply" if result == "ok" else "plan_revision",
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
        PLANNED_CSS.rstrip(),
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
