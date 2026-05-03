#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
RESEARCH_DIR = BASE / "research"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

CANDIDATES = RESEARCH_DIR / "target-family-candidates.jsonl"
TARGET_FAMILY = "community.onboarding_experience"
DESIGN_ID = "learning-v2-community-onboarding-probe-design-v0"

SCAN_FILES = [
    "public/index.html",
    "components/nav.html",
    "public/about.html",
    "public/join.html",
    "public/gallery.html",
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

def load_jsonl(path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows

def main():
    state = load_json(STATE, default={})
    policy = state.get("self_evolution_policy") or {}
    integrity = state.get("last_system_integrity") or {}
    candidates = load_jsonl(CANDIDATES)

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

    matched = [c for c in candidates if c.get("target_family") == TARGET_FAMILY]
    if not matched:
        failures.append(f"missing_target_family_candidate:{TARGET_FAMILY}")

    candidate = matched[-1] if matched else {}

    design = {
        "generated_at": now_iso(),
        "design_id": DESIGN_ID,
        "result": "ok" if not failures else "blocked",
        "target_family": TARGET_FAMILY,
        "candidate_id": candidate.get("candidate_id"),
        "topic": candidate.get("topic"),
        "pattern_count": candidate.get("pattern_count"),
        "principles": candidate.get("principles") or [],
        "recommended_stage": "community_onboarding_probe",
        "recommended_probe_script": "learning-v2-community-onboarding-experience-probe.py",
        "probe_mode": "observe_only",
        "purpose": "Detect whether the BLXST / HADO website gives new parents and players a clear first successful action, low-friction onboarding path, and motivation-to-action bridge.",
        "scan_files": SCAN_FILES,
        "observation_dimensions": [
            {
                "dimension": "first_successful_action",
                "question": "Can a first-time parent or player quickly understand the first useful action to take?",
                "signals": [
                    "clear join / try / learn-more call-to-action",
                    "visible next-step wording",
                    "low ambiguity around what happens after clicking"
                ]
            },
            {
                "dimension": "onboarding_sequence",
                "question": "Does the page sequence learning, trust, and action in a low-cognitive-load order?",
                "signals": [
                    "what HADO is",
                    "why it matters",
                    "who it is for",
                    "how to join or try",
                    "where to see examples"
                ]
            },
            {
                "dimension": "motivation_to_next_step",
                "question": "Does the page connect parent/player motivation to a practical next step?",
                "signals": [
                    "parent-child connection",
                    "youth growth / confidence / team spirit",
                    "community participation",
                    "clear action path"
                ]
            }
        ],
        "finding_schema": {
            "file": "path scanned",
            "dimension": "first_successful_action / onboarding_sequence / motivation_to_next_step",
            "status": "ok / review / missing",
            "severity": "low / medium / high",
            "evidence": "short observed text or missing signal",
            "recommendation": "observe-only recommendation, no source change"
        },
        "guardrails": [
            "Probe must not modify website source.",
            "Probe must not write state.json.",
            "Probe must not commit, push, or deploy.",
            "Probe only writes reports.",
            "Any future source change must go through proposal and controlled source-change gate."
        ],
        "policy": {
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "design_only": True
        },
        "failures": failures
    }

    out_json = REPORT_DIR / f"community-onboarding-probe-design-{stamp()}.json"
    out_md = REPORT_DIR / f"community-onboarding-probe-design-{stamp()}.md"

    out_json.write_text(json.dumps(design, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("# Learning V2 Community Onboarding Probe Design")
    lines.append("")
    lines.append(f"- generated_at: `{design['generated_at']}`")
    lines.append(f"- design_id: `{DESIGN_ID}`")
    lines.append(f"- result: `{design['result']}`")
    lines.append(f"- target_family: `{TARGET_FAMILY}`")
    lines.append(f"- recommended_stage: `{design['recommended_stage']}`")
    lines.append(f"- recommended_probe_script: `{design['recommended_probe_script']}`")
    lines.append("- probe_mode: `observe_only`")
    lines.append("- state_written: `false`")
    lines.append("- business_source_written: `false`")
    lines.append("")
    lines.append("## Principles")
    lines.append("")
    for p in design["principles"]:
        lines.append(f"- {p}")
    lines.append("")
    lines.append("## Observation dimensions")
    lines.append("")
    for d in design["observation_dimensions"]:
        lines.append(f"### `{d['dimension']}`")
        lines.append("")
        lines.append(d["question"])
        lines.append("")
        for s in d["signals"]:
            lines.append(f"- {s}")
        lines.append("")
    lines.append("## Guardrails")
    lines.append("")
    for g in design["guardrails"]:
        lines.append(f"- {g}")
    lines.append("")
    if failures:
        lines.append("## Failures")
        lines.append("")
        for f in failures:
            lines.append(f"- {f}")
        lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("community_onboarding_probe_design =", design["result"])
    print("design_id =", DESIGN_ID)
    print("target_family =", TARGET_FAMILY)
    print("candidate_id =", candidate.get("candidate_id"))
    print("pattern_count =", candidate.get("pattern_count"))
    print("recommended_stage =", design["recommended_stage"])
    print("recommended_probe_script =", design["recommended_probe_script"])
    print("design_json =", out_json)
    print("design_md =", out_md)
    print("state_written = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if failures:
        print()
        print("failures:")
        for f in failures:
            print(" ", f)
        raise SystemExit(2)

if __name__ == "__main__":
    main()
