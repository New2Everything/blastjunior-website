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

FINALIZER_ID = "learning-v2-research-derived-manual-review-finalizer-v0"

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

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="park current research-derived manual review item and return to idle")
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

    target_family = state.get("current_target_family")
    current_topic = state.get("current_topic")
    current_stage = state.get("current_stage")

    resolver_path, resolver = latest_report("research-derived-probe-resolver-apply-*.json")
    probe_path = resolver.get("probe_report") if resolver else None

    failures = []

    if policy.get("mode") != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{policy.get('mode')}")
    if current_topic != "research-derived":
        failures.append(f"current_topic_not_research_derived:{current_topic}")
    if current_stage != "manual_review_required":
        failures.append(f"current_stage_not_manual_review_required:{current_stage}")
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
    if not resolver_path:
        failures.append("missing_latest_research_derived_resolver_apply_report")
    if resolver and resolver.get("target_family") != target_family:
        failures.append(f"resolver_target_family_mismatch:{resolver.get('target_family')}")
    if resolver and resolver.get("decision") != "manual_review_required":
        failures.append(f"resolver_decision_not_manual_review_required:{resolver.get('decision')}")
    if resolver and int(resolver.get("review_recommended_count") or 0) <= 0:
        failures.append("resolver_review_recommended_count_not_positive")

    result = "ok" if not failures else "blocked"

    item_id = f"manual-review-{str(target_family or 'unknown').replace('/', '-')}-{stamp()}"
    manual_item = {
        "at": now_iso(),
        "item_id": item_id,
        "target_family": target_family,
        "topic": "research-derived",
        "stage_before": resolver.get("stage_before") if resolver else current_stage,
        "stage_after": "manual_review_required",
        "status": "pending_manual_review",
        "reason": "research-derived observe-only probe found review-recommended gaps",
        "resolver_report": str(resolver_path) if resolver_path else None,
        "probe_report": probe_path,
        "review_recommended_count": resolver.get("review_recommended_count") if resolver else None,
        "signal_present_count": resolver.get("signal_present_count") if resolver else None,
        "recommended_next_step": "manual review required before any source-change proposal",
        "source_change_allowed_now": False,
        "business_source_written": False,
        "website_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    }

    payload = {
        "generated_at": now_iso(),
        "finalizer_id": FINALIZER_ID,
        "result": result,
        "apply": args.apply,
        "target_family": target_family,
        "current_topic": current_topic,
        "current_stage": current_stage,
        "manual_item": manual_item,
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
    out_json = REPORT_DIR / f"research-derived-manual-review-finalizer-{suffix}-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"research-derived-manual-review-finalizer-{suffix}-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Research-Derived Manual Review Finalizer",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- result: `{result}`",
        f"- apply: `{str(args.apply).lower()}`",
        f"- target_family: `{target_family}`",
        f"- current_stage: `{current_stage}`",
        f"- item_id: `{item_id}`",
        f"- state_written: `{str(payload['policy']['state_written']).lower()}`",
        "- business_source_written: `false`",
        "- website_source_written: `false`",
        "- source_change_gate_opened: `false`",
        "- git_commit: `false`",
        "- git_push: `false`",
        "- deploy: `false`",
    ]

    if failures:
        lines += ["", "## Failures", ""]
        lines += [f"- {x}" for x in failures]

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("research_derived_manual_review_finalizer =", result)
    print("mode =", "apply" if args.apply else "dry_run")
    print("target_family =", target_family)
    print("current_stage =", current_stage)
    print("item_id =", item_id)
    print("resolver_report =", resolver_path)
    print("probe_report =", probe_path)
    print("state_written =", "true" if args.apply and result == "ok" else "false")
    print("business_source_written = false")
    print("website_source_written = false")
    print("source_change_gate_opened = false")
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
        "executor": "research_derived_manual_review_finalizer",
        "stage_before": current_stage,
        "stage_after": None,
        "target_family": target_family,
        "manual_item_id": item_id,
        "source_changed": False,
        "business_source_written": False,
        "website_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    })

    state.setdefault("manual_review_items", [])
    existing = {
        x.get("target_family")
        for x in state["manual_review_items"]
        if isinstance(x, dict)
    }
    if target_family not in existing:
        state["manual_review_items"].append(manual_item)

    state.setdefault("disabled_target_families", [])
    if target_family not in state["disabled_target_families"]:
        state["disabled_target_families"].append(target_family)

    state["last_research_derived_manual_review_finalizer"] = {
        "at": now_iso(),
        "result": "parked_manual_review",
        "target_family": target_family,
        "manual_item_id": item_id,
        "resolver_report": str(resolver_path) if resolver_path else None,
        "probe_report": probe_path,
        "source_changed": False,
        "business_source_written": False,
        "website_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    }

    state["current_topic"] = None
    state["current_stage"] = None
    state["current_target_family"] = None
    state["next_action"] = "Run autonomous discovery for the next non-disabled target family."
    state["updated_at"] = now_iso()

    save_json(STATE, state)

    print("state_updated = true")
    print("manual_review_item_added =", "false" if target_family in existing else "true")
    print("disabled_target_family =", target_family)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
