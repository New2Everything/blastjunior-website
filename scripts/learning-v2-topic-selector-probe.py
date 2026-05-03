#!/usr/bin/env python3
import ast
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

TOPIC_SELECTOR = WORKSPACE / "scripts/learning-v2-topic-selector.py"

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

def run(cmd):
    p = subprocess.run(
        cmd,
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        "cmd": cmd,
        "returncode": p.returncode,
        "stdout": p.stdout,
        "stderr": p.stderr,
        "ok": p.returncode == 0,
    }

def extract_string_lists_from_selector():
    text = TOPIC_SELECTOR.read_text(encoding="utf-8")
    tree = ast.parse(text)

    lists = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and isinstance(node.value, (ast.List, ast.Tuple)):
                    vals = []
                    ok = True
                    for elt in node.value.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            vals.append(elt.value)
                        else:
                            ok = False
                    if ok:
                        lists[target.id] = vals
    return lists

def main():
    state = load_json(STATE, default={})
    failures = []

    mode = (state.get("self_evolution_policy") or {}).get("mode")
    integrity = state.get("last_system_integrity") or {}

    if mode != "learning_observe_only":
        failures.append(f"mode_not_learning_observe_only:{mode}")

    if state.get("learning_cycle_enabled") is not True:
        failures.append(f"learning_cycle_enabled_not_true:{state.get('learning_cycle_enabled')}")

    if state.get("topic_selector_allowed") is not True:
        failures.append(f"topic_selector_allowed_not_true:{state.get('topic_selector_allowed')}")

    if state.get("allow_source_changes") is not False:
        failures.append(f"allow_source_changes_not_false:{state.get('allow_source_changes')}")

    if state.get("allow_git_commit") is not False:
        failures.append(f"allow_git_commit_not_false:{state.get('allow_git_commit')}")

    if state.get("allow_deploy") is not False:
        failures.append(f"allow_deploy_not_false:{state.get('allow_deploy')}")

    if integrity.get("result") != "ok":
        failures.append(f"system_integrity_not_ok:{integrity.get('result')}")

    selector_text = TOPIC_SELECTOR.read_text(encoding="utf-8")
    selector_has_direct_state_write = (
        'state["current_topic"]' in selector_text
        or "state['current_topic']" in selector_text
        or 'state["current_stage"]' in selector_text
        or "state['current_stage']" in selector_text
    )

    lists = extract_string_lists_from_selector()

    report = {
        "generated_at": now_iso(),
        "probe": "learning-v2-topic-selector-probe",
        "result": "ok" if not failures else "blocked",
        "mode": mode,
        "current_topic": state.get("current_topic"),
        "current_stage": state.get("current_stage"),
        "current_target_family": state.get("current_target_family"),
        "learning_cycle_enabled": state.get("learning_cycle_enabled"),
        "topic_selector_allowed": state.get("topic_selector_allowed"),
        "allow_source_changes": state.get("allow_source_changes"),
        "allow_git_commit": state.get("allow_git_commit"),
        "allow_deploy": state.get("allow_deploy"),
        "system_integrity_result": integrity.get("result"),
        "selector_has_direct_state_write": selector_has_direct_state_write,
        "string_lists_found": lists,
        "failures": failures,
        "policy": {
            "state_written": False,
            "business_source_written": False,
            "git_commit": False,
            "git_push": False,
            "deploy": False,
            "probe_only": True
        }
    }

    out = REPORT_DIR / f"topic-selector-probe-{stamp()}.json"
    save_json(out, report)

    print("topic_selector_probe =", report["result"])
    print("probe_report =", out)
    print("mode =", mode)
    print("current_topic =", state.get("current_topic"))
    print("current_stage =", state.get("current_stage"))
    print("selector_has_direct_state_write =", selector_has_direct_state_write)
    print("state_written = false")
    print("business_source_written = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    if lists:
        print()
        print("string_lists_found:")
        for k, v in lists.items():
            print(f"  {k} = {v}")

    if failures:
        print()
        print("failures:")
        for x in failures:
            print(" ", x)
        raise SystemExit(2)

if __name__ == "__main__":
    main()
