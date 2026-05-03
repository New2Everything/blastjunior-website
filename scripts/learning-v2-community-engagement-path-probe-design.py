#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
RESEARCH = BASE / "research"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

DESIGN_ID = "learning-v2-community-engagement-path-probe-design-v0"
TARGET_FAMILY = "community.engagement_path"
RECOMMENDED_PROBE_SCRIPT = "learning-v2-community-engagement-path-probe.py"
CANDIDATE_FILE = RESEARCH / "target-family-candidates.jsonl"

SCAN_FILES = [
    "public/index.html",
    "public/about.html",
    "public/gallery.html",
    "public/news.html",
    "components/nav.html",
]

DIMENSIONS = [
    {
        "dimension": "clear_engagement_next_step",
        "description": "Check whether visitors can identify one clear next action after learning about the community.",
        "expected_evidence": [
            "join, try, contact, register, book, visit, watch, gallery, event, team, parent/student next step"
        ],
        "severity_if_missing": "high",
    },
    {
        "dimension": "low_cognitive_load_sequence",
        "description": "Check whether the engagement path is broken into simple steps rather than scattered choices.",
        "expected_evidence": [
            "numbered steps, short CTA block, sequence language, beginner-friendly guidance"
        ],
        "severity_if_missing": "medium",
    },
    {
        "dimension": "community_social_proof",
        "description": "Check whether the site shows evidence that real people, families, players, teams, or events exist.",
        "expected_evidence": [
            "teams, gallery, event photos, family/player/community wording, HPL, club activity"
        ],
        "severity_if_missing": "medium",
    },
    {
        "dimension": "return_path_after_browsing",
        "description": "Check whether gallery/news/about pages guide users back to a concrete community action.",
        "expected_evidence": [
            "CTA from content pages back to join/contact/try/event path"
        ],
        "severity_if_missing": "medium",
    },
    {
        "dimension": "safe_navigation_to_engagement",
        "description": "Check whether navigation exposes engagement destinations without requiring users to guess.",
        "expected_evidence": [
            "visible nav links to gallery, teams, standings, news, contact, join, events"
        ],
        "severity_if_missing": "low",
    },
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

def read_jsonl(path):
    rows = []
    if not path.exists():
        return rows
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            obj["_jsonl_line"] = i
            rows.append(obj)
        except Exception as e:
            rows.append({"_jsonl_line": i, "_parse_error": str(e)})
    return rows

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

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

    for key in [
        "source_changes_allowed",
        "git_commit_allowed",
        "git_push_allowed",
        "deploy_allowed",
    ]:
        if policy.get(key) is not False:
            failures.append(f"policy_{key}_not_false:{policy.get(key)}")

    candidates = read_jsonl(CANDIDATE_FILE)
    matched = [x for x in candidates if x.get("target_family") == TARGET_FAMILY]

    if not matched:
        failures.append(f"target_family_candidate_missing:{TARGET_FAMILY}")

    candidate = matched[-1] if matched else None

    if candidate:
        if candidate.get("risk") != "low":
            failures.append(f"candidate_risk_not_low:{candidate.get('risk')}")
        if candidate.get("observe_only_first") is not True:
            failures.append(f"candidate_observe_only_first_not_true:{candidate.get('observe_only_first')}")
        if candidate.get("activation_allowed_now") is not True:
            failures.append(f"candidate_activation_allowed_now_not_true:{candidate.get('activation_allowed_now')}")
        if candidate.get("recommended_probe_script") != RECOMMENDED_PROBE_SCRIPT:
            failures.append(f"candidate_recommended_probe_script_mismatch:{candidate.get('recommended_probe_script')}")

    scan_file_status = []
    for rel in SCAN_FILES:
        p = WORKSPACE / rel
        scan_file_status.append({
            "path": rel,
            "exists": p.exists(),
            "is_file": p.is_file(),
            "size_bytes": p.stat().st_size if p.exists() and p.is_file() else None,
        })

    missing_scan_files = [x["path"] for x in scan_file_status if not x["exists"]]
    if missing_scan_files:
        warnings.append(f"scan_files_missing:{missing_scan_files}")

    result = "ok" if not failures else "blocked"

    out_json = REPORT_DIR / f"community-engagement-path-probe-design-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"community-engagement-path-probe-design-{stamp()}.md"

    payload = {
        "generated_at": now_iso(),
        "design_id": DESIGN_ID,
        "result": result,
        "target_family": TARGET_FAMILY,
        "candidate": candidate,
        "recommended_probe_script": RECOMMENDED_PROBE_SCRIPT,
        "scan_files": SCAN_FILES,
        "scan_file_status": scan_file_status,
        "dimensions": DIMENSIONS,
        "probe_should_output": {
            "result": "ok_or_blocked",
            "target_family": TARGET_FAMILY,
            "scan_files": SCAN_FILES,
            "finding_count": "integer",
            "review_or_missing_count": "integer",
            "high_or_medium_count": "integer",
            "findings": "list of file/dimension/status/severity/evidence/missing/recommendation",
            "policy": {
                "observe_only": True,
                "state_written": False,
                "business_source_written": False,
                "git_commit": False,
                "git_push": False,
                "deploy": False,
            }
        },
        "acceptance_criteria_for_probe_script": [
            "Must be observe-only.",
            "Must not write source files.",
            "Must not write state.",
            "Must scan only declared low-risk HTML/component files.",
            "Must output JSON report and markdown summary.",
            "Must classify findings by dimension/status/severity.",
            "Must keep git_commit/git_push/deploy false.",
            "Must not open source-change gate.",
        ],
        "recommended_next_step": "build_community_engagement_path_observe_only_probe" if result == "ok" else "fix_probe_design_blockers",
        "policy": {
            "design_only": True,
            "state_written": False,
            "business_source_written": False,
            "source_change_gate_opened": False,
            "human_review_required": False,
            "machine_policy_gate": True,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
        "warnings": warnings,
        "failures": failures,
    }

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Community Engagement Path Probe Design")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- design_id: `{DESIGN_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- target_family: `{TARGET_FAMILY}`")
    lines.append(f"- recommended_probe_script: `{RECOMMENDED_PROBE_SCRIPT}`")
    lines.append(f"- recommended_next_step: `{payload['recommended_next_step']}`")
    lines.append("- design_only: `true`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("- source_change_gate_opened: `false`")
    lines.append("- human_review_required: `false`")
    lines.append("- machine_policy_gate: `true`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append("")
    lines.append("## Dimensions")
    for d in DIMENSIONS:
        lines.append(f"- `{d['dimension']}` severity_if_missing=`{d['severity_if_missing']}`")
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

    print("community_engagement_path_probe_design =", result)
    print("target_family =", TARGET_FAMILY)
    print("recommended_probe_script =", RECOMMENDED_PROBE_SCRIPT)
    print("dimension_count =", len(DIMENSIONS))
    print("scan_file_count =", len(SCAN_FILES))
    print("recommended_next_step =", payload["recommended_next_step"])
    print("state_written = False")
    print("business_source_written = False")
    print("source_change_gate_opened = False")
    print("human_review_required = False")
    print("machine_policy_gate = True")
    print("git_commit = False")
    print("git_push = False")
    print("deploy = False")
    print("report_json =", out_json)
    print("report_md =", out_md)
    if warnings:
        print("warnings =", json.dumps(warnings, ensure_ascii=False))
    if failures:
        print("failures =", json.dumps(failures, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
