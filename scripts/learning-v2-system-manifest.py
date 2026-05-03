#!/usr/bin/env python3
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
STATE = BASE / "state.json"
SNAPSHOT_DIR = BASE / "snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

CORE_SCRIPTS = [
    "learning-v2-dispatch.py",
    "learning-v2-topic-selector.py",
    "learning-v2-discover-executor.py",
    "learning-v2-simplicity-audit.py",
    "learning-v2-validate-executor.py",
    "learning-v2-apply-guardrails.py",
    "learning-v2-auto-apply-executor.py",
    "learning-v2-post-apply-validator.py",
    "learning-v2-outcome-recorder.py",
    "learning-v2-mode.py",
    "learning-v2-doctor.py",
    "learning-v2-change-ledger.py",
    "learning-v2-release-planner.py",
    "learning-v2-deploy-observer.py",
]

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def run(cmd):
    r = subprocess.run(
        cmd,
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return {
        "cmd": " ".join(cmd),
        "returncode": r.returncode,
        "stdout": r.stdout.strip(),
        "stderr": r.stderr.strip(),
    }

def load_state():
    return json.loads(STATE.read_text(encoding="utf-8"))

def save_state(state):
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def main():
    script_dir = WORKSPACE / "scripts"
    scripts = sorted(script_dir.glob("learning-v2-*.py"))

    items = []
    for p in scripts:
        rel = str(p.relative_to(WORKSPACE))
        ignore = run(["git", "check-ignore", "-v", rel])
        tracked = run(["git", "ls-files", "--stage", "--", rel])
        status = run(["git", "status", "--short", "--untracked-files=all", "--", rel])

        role = "core" if p.name in CORE_SCRIPTS else "support"

        items.append({
            "path": rel,
            "name": p.name,
            "role": role,
            "exists": p.exists(),
            "size_bytes": p.stat().st_size,
            "executable": bool(p.stat().st_mode & 0o111),
            "sha256": sha256_file(p),
            "git_ignored": ignore["returncode"] == 0,
            "git_ignore_reason": ignore["stdout"],
            "git_tracked": bool(tracked["stdout"]),
            "git_status": status["stdout"],
        })

    missing_core = [
        name for name in CORE_SCRIPTS
        if not (script_dir / name).exists()
    ]

    ignored_core = [
        x for x in items
        if x["role"] == "core" and x["git_ignored"]
    ]

    manifest = {
        "generated_at": now_iso(),
        "mode": "system_manifest_only",
        "source_changed": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
        "total_scripts": len(items),
        "core_scripts": len([x for x in items if x["role"] == "core"]),
        "support_scripts": len([x for x in items if x["role"] == "support"]),
        "missing_core": missing_core,
        "ignored_core_count": len(ignored_core),
        "items": items,
        "packaging_options": {
            "option_a_force_add": {
                "description": "Keep repo .gitignore unchanged and use git add -f for selected learning-v2 scripts when intentionally releasing.",
                "pros": ["minimal repo policy change", "safe for current website repo"],
                "cons": ["release process must remember -f", "less visible to normal git status"],
            },
            "option_b_gitignore_exception": {
                "description": "Modify .gitignore to keep scripts/ ignored generally but unignore scripts/learning-v2-*.py.",
                "pros": ["scripts become visible to git status"],
                "cons": ["changes repo ignore policy", "must ensure other scripts remain ignored"],
            },
            "option_c_move_to_learning_v2_system": {
                "description": "Move/copy releaseable scripts under learning-v2/system/scripts/ and keep runtime scripts local.",
                "pros": ["clean package boundary", "does not fight scripts/ ignore rule"],
                "cons": ["requires path updates or wrapper scripts"],
            },
        },
        "recommended_option": "option_a_force_add for first controlled system release; defer .gitignore changes.",
    }

    out_json = SNAPSHOT_DIR / f"learning-v2-system-manifest-{stamp()}.json"
    out_json.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    out_md = SNAPSHOT_DIR / f"learning-v2-system-manifest-{stamp()}.md"
    lines = []
    lines.append("# Learning V2 System Manifest")
    lines.append("")
    lines.append(f"- generated_at: `{manifest['generated_at']}`")
    lines.append("- mode: `system_manifest_only`")
    lines.append("- source_changed: `false`")
    lines.append("- git_commit: `false`")
    lines.append("- git_push: `false`")
    lines.append("- deploy: `false`")
    lines.append(f"- total_scripts: `{manifest['total_scripts']}`")
    lines.append(f"- core_scripts: `{manifest['core_scripts']}`")
    lines.append(f"- support_scripts: `{manifest['support_scripts']}`")
    lines.append(f"- missing_core: `{len(missing_core)}`")
    lines.append(f"- ignored_core_count: `{manifest['ignored_core_count']}`")
    lines.append("")
    lines.append("## Core scripts")
    lines.append("")
    for x in items:
        if x["role"] != "core":
            continue
        lines.append(f"- `{x['path']}` size=`{x['size_bytes']}` exec=`{x['executable']}` ignored=`{x['git_ignored']}`")
    lines.append("")
    lines.append("## Support scripts")
    lines.append("")
    for x in items:
        if x["role"] != "support":
            continue
        lines.append(f"- `{x['path']}` size=`{x['size_bytes']}` exec=`{x['executable']}` ignored=`{x['git_ignored']}`")
    lines.append("")
    lines.append("## Packaging recommendation")
    lines.append("")
    lines.append(manifest["recommended_option"])
    lines.append("")
    out_md.write_text("\n".join(lines), encoding="utf-8")

    state = load_state()
    state["last_system_manifest"] = {
        "at": now_iso(),
        "snapshot_json": str(out_json),
        "snapshot_report": str(out_md),
        "total_scripts": manifest["total_scripts"],
        "core_scripts": manifest["core_scripts"],
        "support_scripts": manifest["support_scripts"],
        "missing_core": missing_core,
        "ignored_core_count": manifest["ignored_core_count"],
        "recommended_option": manifest["recommended_option"],
        "source_changed": False,
        "git_commit": False,
        "git_push": False,
        "deploy": False,
    }
    state["next_action"] = "Review system manifest. Next: build package plan without commit/push/deploy."
    state["updated_at"] = now_iso()
    save_state(state)

    print("system_manifest_result = ok")
    print("source_changed = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")
    print("snapshot_json =", out_json)
    print("snapshot_report =", out_md)
    print("total_scripts =", manifest["total_scripts"])
    print("core_scripts =", manifest["core_scripts"])
    print("support_scripts =", manifest["support_scripts"])
    print("missing_core =", len(missing_core))
    print("ignored_core_count =", manifest["ignored_core_count"])
    print("recommended_option =", manifest["recommended_option"])

if __name__ == "__main__":
    main()
