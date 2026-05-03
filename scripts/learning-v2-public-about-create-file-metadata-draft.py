#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
CREATE_FILE_METADATA_DIR = BASE / "controlled-create-files"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
CREATE_FILE_METADATA_DIR.mkdir(parents=True, exist_ok=True)

DRAFT_ID = "learning-v2-public-about-create-file-metadata-draft-v0"
TARGET_CANDIDATE_ID = "deferred-public-about-page"
TARGET_FAMILY = "community.engagement_path"
TARGET_FILE = "public/about.html"
METADATA_FILENAME = "public-about-create-file-v0.json"
METADATA_PATH = CREATE_FILE_METADATA_DIR / METADATA_FILENAME

FORBIDDEN_TARGET_FILES = [
    "wrangler.toml",
    "package.json",
    "components/nav.html",
    "components/nav.css",
    "public/index.html",
    "public/gallery.html",
    "public/news.html",
]

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
    files = sorted(REPORT_DIR.glob(pattern))
    if not files:
        return None, {}
    p = files[-1]
    return p, load_json(p, default={})

def latest_snapshot(pattern):
    files = sorted(SNAPSHOT_DIR.glob(pattern))
    return files[-1] if files else None

def find_key(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for value in obj.values():
            found = find_key(value, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = find_key(item, key)
            if found is not None:
                return found
    return None

def build_public_about_metadata():
    body = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>关于兰星少年</title>
  <link rel="stylesheet" href="/assets/css/site.css?v=20260110" />
</head>
<body>
  <main class="about-page" data-controlled-create-file="public-about-page">
    <section class="about-hero" aria-labelledby="about-page-title">
      <p class="eyebrow">LANXING JUNIOR · HADO COMMUNITY</p>
      <h1 id="about-page-title">关于兰星少年</h1>
      <p class="lead about-page-community-path">
        兰星少年是围绕 HADO 运动体验、训练、赛事和社区连接形成的青少年成长空间。
      </p>
    </section>

    <section aria-labelledby="about-community-title">
      <h2 id="about-community-title">我们希望带给孩子什么</h2>
      <p>
        在这里，孩子们不只是体验一项科技运动，也会通过训练、组队、比赛和复盘，建立勇气、规则意识、团队协作和面对胜负的韧性。
      </p>
    </section>

    <section aria-labelledby="about-next-step-title">
      <h2 id="about-next-step-title">下一步可以很简单</h2>
      <p>
        如果你是第一次了解兰星少年，可以先看看 HADO 精彩瞬间，也可以回到首页了解如何开始体验。
      </p>
      <p>
        <a href="/gallery.html">看看 HADO 精彩瞬间</a>
        <span aria-hidden="true"> · </span>
        <a href="/index.html">回到首页</a>
      </p>
    </section>
  </main>
</body>
</html>
"""

    return {
        "change_unit_id": "create-public-about-page-v0",
        "target_candidate_id": TARGET_CANDIDATE_ID,
        "target_family": TARGET_FAMILY,
        "target_file": TARGET_FILE,
        "risk": "low",
        "change_type": "create_file_from_template",
        "change_goal": "Create a simple static about page for the Lanxing Junior community path without changing existing business source files.",
        "allowed_stage": "metadata_draft_only",
        "template": {
            "mode": "create_file_from_template",
            "template_name": "public-about-simple-static-page",
            "template_source": "learning-v2-create-file-lifecycle-extension-v0",
            "body": body,
            "required_sections": [
                "<!DOCTYPE html>",
                "data-controlled-create-file=\"public-about-page\"",
                "id=\"about-page-title\"",
                "about-page-community-path",
                "关于兰星少年"
            ]
        },
        "safety": {
            "target_file_must_not_exist": True,
            "allowed_target_prefixes": ["public/"],
            "forbidden_target_files": FORBIDDEN_TARGET_FILES,
            "max_total_lines": 120,
            "blocked_content_markers": [
                "<script",
                "fetch(",
                "localStorage",
                "onclick=",
                "onsubmit=",
                "wrangler",
                "D1",
                "KV",
                "R2"
            ],
            "git_commit": False,
            "git_push": False,
            "deploy": False
        },
        "acceptance": {
            "expected_target_file": TARGET_FILE,
            "required_markers": [
                "data-controlled-create-file=\"public-about-page\"",
                "id=\"about-page-title\"",
                "about-page-community-path",
                "关于兰星少年"
            ],
            "created_file_must_be_only_delta": True,
            "ledger_acceptance_required": True
        }
    }

def validate_metadata_shape(meta):
    failures = []
    warnings = []

    body = (meta.get("template") or {}).get("body") or ""
    safety = meta.get("safety") or {}
    acceptance = meta.get("acceptance") or {}

    if meta.get("target_candidate_id") != TARGET_CANDIDATE_ID:
        failures.append(f"target_candidate_id_unexpected:{meta.get('target_candidate_id')}")

    if meta.get("target_family") != TARGET_FAMILY:
        failures.append(f"target_family_unexpected:{meta.get('target_family')}")

    if meta.get("target_file") != TARGET_FILE:
        failures.append(f"target_file_unexpected:{meta.get('target_file')}")

    if meta.get("risk") != "low":
        failures.append(f"risk_not_low:{meta.get('risk')}")

    if meta.get("change_type") != "create_file_from_template":
        failures.append(f"change_type_invalid:{meta.get('change_type')}")

    if meta.get("allowed_stage") != "metadata_draft_only":
        failures.append(f"allowed_stage_not_metadata_draft_only:{meta.get('allowed_stage')}")

    if (WORKSPACE / TARGET_FILE).exists():
        failures.append(f"target_file_already_exists:{TARGET_FILE}")

    if METADATA_PATH.exists():
        warnings.append(f"metadata_path_already_exists:{METADATA_PATH}")

    if safety.get("target_file_must_not_exist") is not True:
        failures.append("target_file_must_not_exist_not_true")

    for key in ["git_commit", "git_push", "deploy"]:
        if safety.get(key) is not False:
            failures.append(f"safety_{key}_not_false:{safety.get(key)}")

    if not body.strip():
        failures.append("template_body_empty")

    for marker in safety.get("blocked_content_markers") or []:
        if str(marker).lower() in body.lower():
            failures.append(f"blocked_content_marker_found:{marker}")

    for marker in acceptance.get("required_markers") or []:
        if marker not in body:
            failures.append(f"required_marker_missing_from_body:{marker}")

    if acceptance.get("created_file_must_be_only_delta") is not True:
        failures.append("created_file_must_be_only_delta_not_true")

    if acceptance.get("ledger_acceptance_required") is not True:
        failures.append("ledger_acceptance_required_not_true")

    line_count = len(body.splitlines())
    max_lines = safety.get("max_total_lines")
    if isinstance(max_lines, int) and line_count > max_lines:
        failures.append(f"body_line_count_exceeds_max:{line_count}>{max_lines}")

    return failures, warnings

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write metadata draft to controlled-create-files")
    args = ap.parse_args()

    run_stamp = stamp()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    readiness_path, readiness = latest_report("create-file-metadata-draft-readiness-*.json")
    template_validator_path, template_validator = latest_report("controlled-change-new-file-template-validator-*.json")
    ledger_path, ledger = latest_report("controlled-change-generic-create-file-ledger-acceptance-*.json")
    extension_closed_snapshot = latest_snapshot("learning-v2-create-file-lifecycle-extension-closed-*.md")
    integrity_path, integrity = latest_report("system-integrity-*.json")
    drift_path, drift = latest_report("system-drift-audit-*.json")

    failures = []
    warnings = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")

    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_false:{state.get('allow_source_changes')}")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    for key in ["source_changes_allowed", "git_commit_allowed", "git_push_allowed", "deploy_allowed"]:
        if policy.get(key) is not False:
            failures.append(f"policy_{key}_not_false:{policy.get(key)}")

    for label, path, report in [
        ("metadata_draft_readiness", readiness_path, readiness),
        ("new_file_template_validator", template_validator_path, template_validator),
        ("create_file_ledger_acceptance", ledger_path, ledger),
        ("system_integrity", integrity_path, integrity),
    ]:
        if not path:
            failures.append(f"missing_{label}_report")
        elif report.get("result") != "ok":
            failures.append(f"{label}_not_ok:{report.get('result')}")

    if not extension_closed_snapshot:
        failures.append("missing_create_file_lifecycle_extension_closed_snapshot")

    integrity_drift_count = integrity.get("drift_count")
    if integrity_drift_count is None:
        integrity_drift_count = find_key(integrity, "drift_count")
    if integrity_drift_count is None:
        integrity_drift_count = drift.get("drift_count")

    business_freeze_stable = integrity.get("business_freeze_stable")
    if business_freeze_stable is None:
        business_freeze_stable = find_key(integrity, "business_freeze_stable")
    if business_freeze_stable is None:
        business_freeze_stable = drift.get("business_freeze_stable")

    if integrity_drift_count != 0:
        failures.append(f"drift_count_not_zero:{integrity_drift_count}")

    if business_freeze_stable is not True:
        failures.append(f"business_freeze_not_stable:{business_freeze_stable}")

    if readiness.get("readiness_status") != "ready_for_metadata_draft_only":
        failures.append(f"readiness_status_not_ready:{readiness.get('readiness_status')}")

    if readiness.get("target_file") != TARGET_FILE:
        failures.append(f"readiness_target_file_unexpected:{readiness.get('target_file')}")

    if readiness.get("target_file_exists") is not False:
        failures.append(f"readiness_target_file_exists_not_false:{readiness.get('target_file_exists')}")

    if readiness.get("metadata_written") is not False:
        failures.append(f"readiness_metadata_written_not_false:{readiness.get('metadata_written')}")

    metadata = build_public_about_metadata()
    meta_failures, meta_warnings = validate_metadata_shape(metadata)
    failures.extend(meta_failures)
    warnings.extend(meta_warnings)

    metadata_written = False
    written_metadata_path = None

    if args.apply and not failures:
        save_json(METADATA_PATH, metadata)
        metadata_written = True
        written_metadata_path = str(METADATA_PATH)

    result = "ok" if not failures else "blocked"

    recommended_next_step = (
        "run_new_file_template_validator_for_public_about_metadata"
        if metadata_written
        else "apply_public_about_create_file_metadata_draft_no_source_write"
        if result == "ok"
        else "fix_public_about_metadata_draft_blockers"
    )

    out_json = REPORT_DIR / f"public-about-create-file-metadata-draft-{'apply' if args.apply else 'dry-run'}-{run_stamp}.json"
    out_md = SNAPSHOT_DIR / f"public-about-create-file-metadata-draft-{'apply' if args.apply else 'dry-run'}-{run_stamp}.md"
    preview_json = SNAPSHOT_DIR / f"public-about-create-file-metadata-preview-{run_stamp}.json"

    save_json(preview_json, metadata)

    payload = {
        "generated_at": now_iso(),
        "draft_id": DRAFT_ID,
        "result": result,
        "apply": args.apply,
        "draft_mode": "metadata_draft_apply" if args.apply else "metadata_draft_preview_only",
        "target_candidate_id": TARGET_CANDIDATE_ID,
        "target_family": TARGET_FAMILY,
        "target_file": TARGET_FILE,
        "target_file_exists": (WORKSPACE / TARGET_FILE).exists(),
        "metadata_path": str(METADATA_PATH),
        "metadata_preview_path": str(preview_json),
        "metadata_written": metadata_written,
        "written_metadata_path": written_metadata_path,
        "source_written": False,
        "state_written": False,
        "business_source_written": False,
        "source_change_gate_opened": False,
        "fourth_loop_started": False,
        "human_review_required": False,
        "machine_policy_gate": True,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "metadata": metadata,
        "metadata_draft_readiness_report": str(readiness_path) if readiness_path else None,
        "new_file_template_validator_report": str(template_validator_path) if template_validator_path else None,
        "create_file_ledger_acceptance_report": str(ledger_path) if ledger_path else None,
        "extension_closed_snapshot": str(extension_closed_snapshot) if extension_closed_snapshot else None,
        "integrity_report": str(integrity_path) if integrity_path else None,
        "recommended_next_step": recommended_next_step,
        "policy": {
            "metadata_draft_only": True,
            "metadata_written": metadata_written,
            "state_written": False,
            "business_source_written": False,
            "source_change_gate_opened": False,
            "fourth_loop_started": False,
            "human_review_required": False,
            "machine_policy_gate": True,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
        "warnings": warnings,
        "failures": failures,
    }

    save_json(out_json, payload)

    lines = []
    lines.append("# Learning V2 Public About Create File Metadata Draft")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- draft_id: `{DRAFT_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- apply: `{str(args.apply).lower()}`")
    lines.append(f"- draft_mode: `{payload['draft_mode']}`")
    lines.append(f"- target_candidate_id: `{TARGET_CANDIDATE_ID}`")
    lines.append(f"- target_family: `{TARGET_FAMILY}`")
    lines.append(f"- target_file: `{TARGET_FILE}`")
    lines.append(f"- target_file_exists: `{str(payload['target_file_exists']).lower()}`")
    lines.append(f"- metadata_path: `{METADATA_PATH}`")
    lines.append(f"- metadata_preview_path: `{preview_json}`")
    lines.append(f"- metadata_written: `{str(metadata_written).lower()}`")
    lines.append("- source_written: `false`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("- source_change_gate_opened: `false`")
    lines.append("- fourth_loop_started: `false`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append(f"- recommended_next_step: `{recommended_next_step}`")
    lines.append("")
    lines.append("## Metadata Summary")
    lines.append(f"- change_unit_id: `{metadata.get('change_unit_id')}`")
    lines.append(f"- allowed_stage: `{metadata.get('allowed_stage')}`")
    lines.append(f"- change_type: `{metadata.get('change_type')}`")
    lines.append(f"- template_name: `{(metadata.get('template') or {}).get('template_name')}`")

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

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("public_about_create_file_metadata_draft =", result)
    print("apply =", args.apply)
    print("draft_mode =", payload["draft_mode"])
    print("target_candidate_id =", TARGET_CANDIDATE_ID)
    print("target_family =", TARGET_FAMILY)
    print("target_file =", TARGET_FILE)
    print("target_file_exists =", payload["target_file_exists"])
    print("metadata_path =", METADATA_PATH)
    print("metadata_preview_path =", preview_json)
    print("metadata_written =", metadata_written)
    print("source_written = False")
    print("state_written = False")
    print("business_source_written = False")
    print("source_change_gate_opened = False")
    print("fourth_loop_started = False")
    print("human_review_required = False")
    print("machine_policy_gate = True")
    print("git_commit = False")
    print("git_push = False")
    print("deploy = False")
    print("recommended_next_step =", recommended_next_step)
    print("report_json =", out_json)
    print("report_md =", out_md)

    if warnings:
        print("warnings =", json.dumps(warnings, ensure_ascii=False))
    if failures:
        print("failures =", json.dumps(failures, ensure_ascii=False, indent=2))
        raise SystemExit(2)

if __name__ == "__main__":
    main()
