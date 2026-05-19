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

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

RESOLVER_ID = "learning-v2-research-derived-probe-resolver-v0"

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

def latest_probe_for_target(target_family):
    safe = str(target_family or "").replace("/", "-")
    files = sorted(REPORT_DIR.glob(f"research-derived-probe-{safe}-*.json"))
    if not files:
        return None, {}
    p = files[-1]
    return p, load_json(p, default={})

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="advance research-derived probe result to track_complete or manual_review_required")
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

    target_family = state.get("current_target_family")
    stage_before = state.get("current_stage")
    probe_path, probe = latest_probe_for_target(target_family)

    failures = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")
    if state.get("current_topic") != "research-derived":
        failures.append(f"current_topic_not_research_derived:{state.get('current_topic')}")
    if not stage_before or not str(stage_before).endswith("_probe"):
        failures.append(f"current_stage_not_probe:{stage_before}")
    if not target_family:
        failures.append("missing_current_target_family")
    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_false:{state.get('allow_source_changes')}")
    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")
    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")
    if integrity.get("result") != "ok":
        failures.append(f"system_integrity_not_ok:{integrity.get('result')}")
    if not probe_path:
        failures.append(f"missing_research_derived_probe_report_for:{target_family}")
    if probe and probe.get("result") != "ok":
        failures.append(f"probe_result_not_ok:{probe.get('result')}")
    if probe and probe.get("target_family") != target_family:
        failures.append(f"probe_target_family_mismatch:{probe.get('target_family')}")

    review_count = int(probe.get("review_recommended_count") or 0) if probe else 0
    signal_count = int(probe.get("signal_present_count") or 0) if probe else 0

    if failures:
        decision = "blocked"
        stage_after = stage_before
        next_action = "Fix resolver blockers before continuing."
    elif review_count > 0:
        decision = "manual_review_required"
        stage_after = "manual_review_required"
        next_action = "Park this research-derived item into manual_review_items, then return to idle."
    else:
        decision = "track_complete"
        stage_after = "track_complete"
        next_action = "Finalize this completed observe-only research-derived target to idle."

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "resolver_id": RESOLVER_ID,
        "result": result,
        "apply": args.apply,
        "target_family": target_family,
        "stage_before": stage_before,
        "stage_after": stage_after,
        "decision": decision,
        "probe_report": str(probe_path) if probe_path else None,
        "review_recommended_count": review_count,
        "signal_present_count": signal_count,
        "policy": {
            "state_written": bool(args.apply and result == "ok"),
            "business_source_written": False,
            "website_source_written": False,
            "source_change_gate_opened": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        },
        "failures": failures,
    }

    suffix = "apply" if args.apply else "dry-run"
    out_json = REPORT_DIR / f"research-derived-probe-resolver-{suffix}-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"research-derived-probe-resolver-{suffix}-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Research-Derived Probe Resolver",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- result: `{result}`",
        f"- apply: `{str(args.apply).lower()}`",
        f"- target_family: `{target_family}`",
        f"- stage_before: `{stage_before}`",
        f"- stage_after: `{stage_after}`",
        f"- decision: `{decision}`",
        f"- review_recommended_count: `{review_count}`",
        f"- signal_present_count: `{signal_count}`",
        "- business_source_written: `false`",
        "- website_source_written: `false`",
        "- git_commit: `false`",
        "- git_push: `false`",
        "- deploy: `false`",
    ]

    if failures:
        lines += ["", "## Failures", ""]
        lines += [f"- {x}" for x in failures]

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("research_derived_probe_resolver =", result)
    print("mode =", "apply" if args.apply else "dry_run")
    print("target_family =", target_family)
    print("stage_before =", stage_before)
    print("stage_after =", stage_after)
    print("decision =", decision)
    print("probe_report =", probe_path)
    print("review_recommended_count =", review_count)
    print("signal_present_count =", signal_count)
    print("state_written =", "true" if args.apply and result == "ok" else "false")
    print("business_source_written = false")
    print("website_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    print("report_json =", out_json)
    print("report_md =", out_md)

    if failures:
        print("failures =", json.dumps(failures, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    if not args.apply:
        return 0

    state.setdefault("history", [])
    state["history"].append({
        "at": now_iso(),
        "executor": "research_derived_probe_resolver",
        "stage_before": stage_before,
        "stage_after": stage_after,
        "target_family": target_family,
        "decision": decision,
        "probe_report": str(probe_path),
        "source_changed": False,
        "business_source_written": False,
        "website_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    })

    state["last_research_derived_probe_resolver"] = {
        "at": now_iso(),
        "result": decision,
        "target_family": target_family,
        "stage_before": stage_before,
        "stage_after": stage_after,
        "probe_report": str(probe_path),
        "review_recommended_count": review_count,
        "signal_present_count": signal_count,
        "source_changed": False,
        "business_source_written": False,
        "website_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    }

    if decision == "track_complete":
        track = {
            "at": now_iso(),
            "track_id": target_family,
            "topic": "research-derived",
            "stage_before": stage_before,
            "stage_after": "track_complete",
            "result": "track_complete",
            "reason": "observe-only research-derived probe found no review-recommended gaps",
            "probe_report": str(probe_path),
            "source_changed": False,
            "business_source_written": False,
            "website_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
        }
        state.setdefault("completed_tracks", [])
        existing = {x.get("track_id") for x in state["completed_tracks"] if isinstance(x, dict)}
        if target_family not in existing:
            state["completed_tracks"].append(track)
        state["last_track_complete"] = track

    state["current_stage"] = stage_after
    state["next_action"] = next_action
    state["updated_at"] = now_iso()

    save_json(STATE, state)

    print("state_updated = true")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
