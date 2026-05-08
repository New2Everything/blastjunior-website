#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

APPLY_ID = "learning-v2-opportunity-controlled-apply-v0"

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

def latest_plan_report():
    files = sorted(
        REPORT_DIR.glob("opportunity-controlled-change-plan-*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files[0] if files else None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually apply the controlled change.")
    args = parser.parse_args()

    mode = "apply" if args.apply else "dry_run"

    plan_path = latest_plan_report()
    if not plan_path:
        raise SystemExit("NO_CONTROLLED_CHANGE_PLAN_FOUND")

    plan_payload = load_json(plan_path, default={}) or {}
    plan = plan_payload.get("plan") or {}

    failures = []
    warnings = []

    if plan_payload.get("result") != "ok":
        failures.append(f"plan_not_ok:{plan_payload.get('result')}")

    target_rel = plan.get("target_file")
    planned_content = plan.get("planned_content")

    if target_rel != "public/assets/css/site.css":
        failures.append(f"unexpected_target_file:{target_rel}")

    if not planned_content or '@import url("/styles.css");' not in planned_content:
        failures.append("planned_content_missing_expected_import")

    source_styles = WORKSPACE / "public/styles.css"
    if not source_styles.exists():
        failures.append("source_styles_css_missing:public/styles.css")

    target = WORKSPACE / target_rel if target_rel else None

    if target and target.exists():
        warnings.append(f"target_file_already_exists:{target_rel}")

    result = "blocked" if failures else "ok"

    applied = False

    if result == "ok" and args.apply:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(planned_content, encoding="utf-8")
        applied = True

    payload = {
        "generated_at": now_iso(),
        "apply_id": APPLY_ID,
        "mode": mode,
        "result": result,
        "source_plan_report": str(plan_path),
        "target_file": target_rel,
        "change_type": plan.get("change_type"),
        "applied": applied,
        "failures": failures,
        "warnings": warnings,
        "policy": {
            "website_files_changed": applied,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "restore_cloudflare_auto_deploy": False,
        },
        "recommended_next_stage": "post_apply_validation" if applied else "controlled_apply",
    }

    out_json = REPORT_DIR / f"opportunity-controlled-apply-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"opportunity-controlled-apply-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Opportunity Controlled Apply",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- apply_id: `{APPLY_ID}`",
        f"- mode: `{mode}`",
        f"- result: `{result}`",
        f"- applied: `{str(applied).lower()}`",
        f"- source_plan_report: `{payload['source_plan_report']}`",
        f"- target_file: `{target_rel}`",
        f"- recommended_next_stage: `{payload['recommended_next_stage']}`",
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
        f"- website_files_changed: `{str(applied).lower()}`",
        "- git_commit: `false`",
        "- git_push: `false`",
        "- deploy: `false`",
        "- restore_cloudflare_auto_deploy: `false`",
        "",
    ]

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("opportunity_controlled_apply =", result)
    print("mode =", mode)
    print("target_file =", target_rel)
    print("applied =", str(applied).lower())
    print("recommended_next_stage =", payload["recommended_next_stage"])
    print("report_json =", out_json)
    print("report_md =", out_md)
    if failures:
        print("failures =", json.dumps(failures, ensure_ascii=False, indent=2))
    if warnings:
        print("warnings =", json.dumps(warnings, ensure_ascii=False, indent=2))
    print("website_files_changed =", str(applied).lower())
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

if __name__ == "__main__":
    main()
