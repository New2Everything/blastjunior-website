#!/usr/bin/env python3
import argparse, json, subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
RESOLVER = WORKSPACE / "scripts" / "learning-v2-failure-context-resolver.py"
POLICY = WORKSPACE / "projects" / "BLXST-next-action-dispatcher-policy.json"
REPORT_DIR = WORKSPACE / "learning-v2" / "reports"
SNAPSHOT_DIR = WORKSPACE / "learning-v2" / "snapshots"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def latest(pattern):
    files = sorted(REPORT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None

def run_resolver_simulation(name):
    p = subprocess.run(
        ["python3", str(RESOLVER), "--simulate", name],
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    report = None
    for line in p.stdout.splitlines():
        if line.startswith("report_json ="):
            report = line.split("=", 1)[1].strip()
    if p.returncode != 0 or not report:
        raise RuntimeError("resolver_failed_or_report_missing\nSTDOUT:\n" + p.stdout + "\nSTDERR:\n" + p.stderr)
    return Path(report), load_json(report)

def load_resolver_report(args):
    if args.simulate:
        return run_resolver_simulation(args.simulate)
    if args.input_report:
        p = Path(args.input_report)
        return p, load_json(p)
    p = latest("learning-v2-failure-context-resolver-*.json")
    if not p:
        raise SystemExit("BLOCKED: no failure resolver report found")
    return p, load_json(p)

def select_action(resolution, policy):
    families = list(resolution.get("next_action_families") or [])
    known = policy.get("next_action_families_non_exhaustive") or {}
    priority = policy.get("priority_order_non_exhaustive") or []

    candidates = []
    warnings = []

    for family in families:
        spec = known.get(family)
        if spec:
            candidates.append({
                "family": family,
                "known_policy_family": True,
                "action_type": spec.get("action_type"),
                "recommended_command": spec.get("recommended_command"),
                "meaning": spec.get("meaning")
            })
        else:
            warnings.append("unknown_next_action_family:" + str(family))

    if warnings:
        for fallback in ["triage_unknown_state", "do_not_mutate"]:
            spec = known.get(fallback, {})
            candidates.append({
                "family": fallback,
                "known_policy_family": True,
                "action_type": spec.get("action_type", "triage"),
                "recommended_command": spec.get("recommended_command", "triage unknown state"),
                "meaning": spec.get("meaning", "Unknown family fallback")
            })

    if not candidates:
        for fallback in ["triage_unknown_state", "do_not_mutate"]:
            spec = known.get(fallback, {})
            candidates.append({
                "family": fallback,
                "known_policy_family": True,
                "action_type": spec.get("action_type", "triage"),
                "recommended_command": spec.get("recommended_command", "triage unknown state"),
                "meaning": spec.get("meaning", "No action family fallback")
            })
        warnings.append("no_next_action_family_found")

    def rank(c):
        try:
            return priority.index(c["family"])
        except ValueError:
            return 999

    selected = sorted(candidates, key=rank)[0]

    return selected, candidates, warnings

def write_report(source, resolver_payload, dispatch):
    ts = stamp()
    jp = REPORT_DIR / f"learning-v2-autonomous-next-action-dispatcher-{ts}.json"
    mp = SNAPSHOT_DIR / f"learning-v2-autonomous-next-action-dispatcher-{ts}.md"
    jp.write_text(json.dumps(dispatch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mp.write_text(
        "# Learning V2 Autonomous Next-Action Dispatcher\n\n"
        f"- selected_next_action: `{dispatch['selected_next_action']['family']}`\n"
        f"- resolved_status: `{dispatch['resolver_resolution'].get('resolved_status')}`\n"
        "- execution_allowed: `false`\n"
        "- mutation_allowed: `false`\n"
        "- deploy: `false`\n",
        encoding="utf-8"
    )
    return jp, mp

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-report")
    ap.add_argument("--simulate", choices=["ok","unknown_resource","no_auth","hard_failure","unexpected_status"])
    args = ap.parse_args()

    policy = load_json(POLICY)
    source_path, resolver_payload = load_resolver_report(args)
    resolution = resolver_payload.get("resolution") or resolver_payload

    selected, candidates, warnings = select_action(resolution, policy)

    dispatch = {
        "generated_at": now_iso(),
        "script_id": "learning-v2-autonomous-next-action-dispatcher-v0",
        "mode": "dry_run",
        "source_report": str(source_path),
        "policy": {
            "path": str(POLICY),
            "policy_id": policy.get("policy_id"),
            "policy_driven": policy.get("policy_driven"),
            "examples_are_non_exhaustive": policy.get("examples_are_non_exhaustive"),
            "not_auto_repair": policy.get("not_auto_repair")
        },
        "resolver_resolution": resolution,
        "selected_next_action": selected,
        "candidate_actions": candidates,
        "warnings": sorted(set(warnings)),
        "why_selected": "Selected by policy priority order from resolver next_action_families.",
        "why_not_execute": "Dispatcher is recommendation-only and cannot execute mutation or repair.",
        "safety": {
            "recommendation_only": True,
            "execution_allowed": False,
            "mutation_allowed": False,
            "state_written": False,
            "website_source_written": False,
            "d1_written": False,
            "r2_written": False,
            "kv_written": False,
            "worker_changed": False,
            "cloudflare_mutation": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False
        }
    }

    jp, mp = write_report(source_path, resolver_payload, dispatch)

    print("autonomous_next_action_dispatcher = ok")
    print("resolved_status =", resolution.get("resolved_status"))
    print("selected_next_action =", selected.get("family"))
    print("execution_allowed = false")
    print("mutation_allowed = false")
    print("report_json =", jp)
    print("report_md =", mp)
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

if __name__ == "__main__":
    main()
