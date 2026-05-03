#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

GUARD_ID = "learning-v2-controlled-change-duplication-guard-v1-applied-targets-aware"

STATIC_CLOSED = [
    {
        "change_unit_id": "homepage-onboarding",
        "target_family": "community.onboarding_experience",
        "target_file": "public/index.html",
        "source": "legacy_closed_loop_static_seed",
    },
    {
        "change_unit_id": "gallery-next-action",
        "target_family": "community.onboarding_experience",
        "target_file": "public/gallery.html",
        "source": "legacy_closed_loop_static_seed",
    },
    {
        "change_unit_id": "engagement-news-return-path",
        "target_family": "community.engagement_path",
        "target_file": "public/news.html",
        "source": "legacy_closed_loop_static_seed",
    },
]

CANDIDATES = [
    {
        "candidate_id": "candidate-community.engagement_path-20260429-113329",
        "target_family": "community.engagement_path",
        "topic": "community-experience",
        "risk": "low",
        "activation_allowed_now": True,
        "recommended_probe_script": "learning-v2-community-engagement-path-probe.py",
    },
    {
        "candidate_id": "candidate-community.onboarding_experience-20260429-113329",
        "target_family": "community.onboarding_experience",
        "topic": "community-experience",
        "risk": "low",
        "activation_allowed_now": True,
        "recommended_probe_script": "learning-v2-community-onboarding-experience-probe.py",
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

def normalize_applied_target(item):
    # Legacy string entries may be line references like:
    # public/index.html:73:<a ...>
    # They are useful historical notes, but must NOT become closed target files.
    if isinstance(item, str):
        raw = item.strip()
        looks_like_plain_html_path = (
            raw.startswith("public/")
            and raw.endswith(".html")
            and ":" not in raw
            and "<" not in raw
            and ">" not in raw
        )

        if looks_like_plain_html_path:
            return {
                "change_unit_id": None,
                "target_family": None,
                "target_file": raw,
                "source": "state_applied_targets_string_plain_path",
                "legacy_raw": raw,
                "counts_as_closed": True,
            }

        return {
            "change_unit_id": None,
            "target_family": None,
            "target_file": None,
            "source": "state_applied_targets_legacy_string_ignored_for_closure",
            "legacy_raw": raw,
            "counts_as_closed": False,
        }

    if isinstance(item, dict):
        return {
            "change_unit_id": item.get("change_unit_id") or item.get("id") or item.get("target_id"),
            "target_family": item.get("target_family") or item.get("family"),
            "target_file": item.get("target_file") or item.get("path") or item.get("file"),
            "source": "state_applied_targets",
            "legacy_raw": None,
            "counts_as_closed": True,
        }

    return {
        "change_unit_id": None,
        "target_family": None,
        "target_file": None,
        "source": "state_applied_targets_unknown_ignored_for_closure",
        "legacy_raw": str(item),
        "counts_as_closed": False,
    }

def dedupe_entries(entries):
    seen = set()
    out = []
    for item in entries:
        key = (
            item.get("change_unit_id"),
            item.get("target_family"),
            item.get("target_file"),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}

    failures = []
    warnings = []

    if policy.get("mode") not in ["learning_observe_only", None]:
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

    applied_targets = state.get("applied_targets") or []
    applied_entries_all = [normalize_applied_target(x) for x in applied_targets]
    legacy_applied_target_strings = [
        x for x in applied_entries_all
        if x.get("source") == "state_applied_targets_legacy_string_ignored_for_closure"
    ]
    applied_entries = [
        x for x in applied_entries_all
        if x.get("counts_as_closed") is True
    ]

    closed_entries = dedupe_entries(STATIC_CLOSED + applied_entries)

    closed_change_units = sorted(set(
        x.get("change_unit_id") for x in closed_entries if x.get("change_unit_id")
    ))
    closed_target_files = sorted(set(
        x.get("target_file") for x in closed_entries if x.get("target_file")
    ))
    closed_target_families = sorted(set(
        x.get("target_family") for x in closed_entries if x.get("target_family")
    ))

    applied_target_files = sorted(set(
        x.get("target_file") for x in applied_entries if x.get("target_file")
    ))
    applied_change_units = sorted(set(
        x.get("change_unit_id") for x in applied_entries if x.get("change_unit_id")
    ))

    if "public/about.html" not in closed_target_files:
        failures.append("public_about_not_closed_by_duplication_guard")

    if "create-public-about-page-v0" not in closed_change_units:
        failures.append("create_public_about_page_change_unit_not_closed_by_duplication_guard")

    candidate_results = []
    for candidate in CANDIDATES:
        target_family = candidate.get("target_family")
        probe_exists = (WORKSPACE / "scripts" / candidate.get("recommended_probe_script")).exists()

        blockers = []
        candidate_warnings = []

        if not probe_exists:
            blockers.append("recommended_probe_script_missing")

        if target_family == "community.onboarding_experience":
            blockers.append("blocked_by_duplication_guard_onboarding_saturated")

        if target_family == "community.engagement_path":
            candidate_warnings.append("family_has_closed_loop_requires_unresolved_or_deferred_item")

        candidate_results.append({
            **candidate,
            "recommended_probe_script_exists": probe_exists,
            "status": "blocked" if blockers else "candidate_family_available_but_requires_next_loop_plan",
            "blockers": blockers,
            "warnings": candidate_warnings,
        })

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "guard_id": GUARD_ID,
        "result": result,
        "closed_entries": closed_entries,
        "closed_change_units": closed_change_units,
        "closed_target_files": closed_target_files,
        "closed_target_families": closed_target_families,
        "applied_targets_count": len(applied_targets),
        "applied_target_entries_counted_for_closure": len(applied_entries),
        "legacy_applied_target_strings_ignored_count": len(legacy_applied_target_strings),
        "legacy_applied_target_strings_ignored": legacy_applied_target_strings,
        "applied_target_files": applied_target_files,
        "applied_change_units": applied_change_units,
        "candidate_count": len(CANDIDATES),
        "candidate_results": candidate_results,
        "fourth_loop_allowed_now": False,
        "recommended_next_step": "build_next_loop_readiness_auditor",
        "guard_only": True,
        "state_written": False,
        "business_source_written": False,
        "source_change_gate_opened": False,
        "fourth_loop_started": False,
        "human_review_required": False,
        "machine_policy_gate": True,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "recommendation": {
            "fourth_loop_allowed_now": False,
            "next_step": "build_next_loop_readiness_auditor",
        },
        "policy": {
            "guard_only": True,
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

    out_json = REPORT_DIR / f"controlled-change-duplication-guard-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"controlled-change-duplication-guard-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Controlled Change Duplication Guard")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- guard_id: `{GUARD_ID}`")
    lines.append(f"- result: `{result}`")
    lines.append(f"- applied_targets_count: `{len(applied_targets)}`")
    lines.append(f"- closed_change_units: `{closed_change_units}`")
    lines.append(f"- closed_target_files: `{closed_target_files}`")
    lines.append(f"- closed_target_families: `{closed_target_families}`")
    lines.append("- fourth_loop_allowed_now: `false`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("- source_change_gate_opened: `false`")
    lines.append("- fourth_loop_started: `false`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append("")
    lines.append("## Candidate Results")
    for item in candidate_results:
        lines.append(
            f"- `{item.get('candidate_id')}` family=`{item.get('target_family')}` "
            f"status=`{item.get('status')}` blockers=`{item.get('blockers')}` warnings=`{item.get('warnings')}`"
        )

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

    print("controlled_change_duplication_guard =", result)
    print("closed_change_units =", json.dumps(closed_change_units, ensure_ascii=False))
    print("closed_target_files =", json.dumps(closed_target_files, ensure_ascii=False))
    print("closed_target_families =", json.dumps(closed_target_families, ensure_ascii=False))
    print("applied_targets_count =", len(applied_targets))
    print("applied_target_entries_counted_for_closure =", len(applied_entries))
    print("legacy_applied_target_strings_ignored_count =", len(legacy_applied_target_strings))
    print("candidate_count =", len(CANDIDATES))
    print("fourth_loop_allowed_now = False")
    print("recommended_next_step = build_next_loop_readiness_auditor")
    print("guard_only = True")
    print("state_written = False")
    print("business_source_written = False")
    print("source_change_gate_opened = False")
    print("fourth_loop_started = False")
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
        raise SystemExit(2)

if __name__ == "__main__":
    main()
