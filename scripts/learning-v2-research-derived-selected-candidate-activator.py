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
SCRIPT_DIR = WORKSPACE / "scripts"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

ACTIVATOR_ID = "learning-v2-research-derived-selected-candidate-activator-v0"

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

def safe_script_name(name):
    if not name:
        return False
    if "/" in name or "\\" in name:
        return False
    if not name.startswith("learning-v2-"):
        return False
    if not name.endswith("-probe.py"):
        return False
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    return all(ch in allowed for ch in name)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="seed selected research-derived candidate into state")
    args = ap.parse_args()

    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}

    discovery_path, discovery = latest_report("autonomous-target-discovery-*.json")
    selected = discovery.get("selected_candidate") if isinstance(discovery.get("selected_candidate"), dict) else None

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
    if not discovery_path:
        failures.append("missing_autonomous_target_discovery_report")
    if discovery.get("discovery_status") != "ready_candidate_found":
        failures.append(f"discovery_status_not_ready_candidate_found:{discovery.get('discovery_status')}")
    if not selected:
        failures.append("missing_selected_candidate")
    else:
        if selected.get("topic") != "research-derived":
            failures.append(f"selected_topic_not_research_derived:{selected.get('topic')}")
        if not selected.get("target_family"):
            failures.append("selected_missing_target_family")
        if not selected.get("recommended_stage"):
            failures.append("selected_missing_recommended_stage")
        script = selected.get("recommended_probe_script")
        if not safe_script_name(script):
            failures.append(f"unsafe_or_missing_probe_script:{script}")
        elif not (SCRIPT_DIR / script).exists():
            failures.append(f"probe_script_missing:{script}")
        if selected.get("recommended_probe_script_exists") is not True:
            failures.append("selected_probe_script_exists_not_true")
        if selected.get("selector_ready") is not True:
            failures.append("selected_selector_ready_not_true")

    result = "ok" if not failures else "blocked"

    payload = {
        "generated_at": now_iso(),
        "activator_id": ACTIVATOR_ID,
        "result": result,
        "apply": args.apply,
        "discovery_report": str(discovery_path) if discovery_path else None,
        "selected_candidate": selected,
        "stage_after": selected.get("recommended_stage") if selected else None,
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
    out_json = REPORT_DIR / f"research-derived-selected-candidate-activator-{suffix}-{stamp()}.json"
    out_md = SNAPSHOT_DIR / f"research-derived-selected-candidate-activator-{suffix}-{stamp()}.md"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Learning V2 Research-Derived Selected Candidate Activator",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- result: `{result}`",
        f"- apply: `{str(args.apply).lower()}`",
        f"- target_family: `{selected.get('target_family') if selected else None}`",
        f"- stage_after: `{payload['stage_after']}`",
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

    print("research_derived_selected_candidate_activator =", result)
    print("mode =", "apply" if args.apply else "dry_run")
    print("discovery_report =", discovery_path)
    print("target_family =", selected.get("target_family") if selected else None)
    print("stage_after =", selected.get("recommended_stage") if selected else None)
    print("probe_script =", selected.get("recommended_probe_script") if selected else None)
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
        "executor": "research_derived_selected_candidate_activator",
        "stage_before": None,
        "stage_after": selected.get("recommended_stage"),
        "target_family": selected.get("target_family"),
        "candidate_id": selected.get("candidate_id"),
        "probe_script": selected.get("recommended_probe_script"),
        "source_changed": False,
        "business_source_written": False,
        "website_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    })

    state["last_research_derived_selected_candidate_activator"] = {
        "at": now_iso(),
        "result": "seeded",
        "target_family": selected.get("target_family"),
        "candidate_id": selected.get("candidate_id"),
        "recommended_stage": selected.get("recommended_stage"),
        "recommended_probe_script": selected.get("recommended_probe_script"),
        "discovery_report": str(discovery_path),
        "source_changed": False,
        "business_source_written": False,
        "website_source_written": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    }

    state["current_topic"] = "research-derived"
    state["current_stage"] = selected.get("recommended_stage")
    state["current_target_family"] = selected.get("target_family")
    state["next_action"] = "Run dispatch to execute research-derived observe-only probe."
    state["updated_at"] = now_iso()

    save_json(STATE, state)

    print("state_updated = true")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
