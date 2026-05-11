#!/usr/bin/env python3
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BASE = WORKSPACE / "learning-v2"
REPORT_DIR = BASE / "reports"
SNAPSHOT_DIR = BASE / "snapshots"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

SCRIPT_ID = "learning-v2-agent-status-v0.2"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def run_cmd(args):
    p = subprocess.run(
        args,
        cwd=str(WORKSPACE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        "cmd": args,
        "returncode": p.returncode,
        "stdout": p.stdout,
        "stderr": p.stderr,
    }

def parse_key_values(text):
    data = {}
    for line in text.splitlines():
        m = re.match(r"^([A-Za-z0-9_.\-/]+)\s*=\s*(.*)$", line.strip())
        if m:
            key, value = m.group(1), m.group(2).strip()
            data[key] = value
    return data

def as_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    s = str(value).strip().lower()
    if s in ("true", "ok", "yes", "1"):
        return True
    if s in ("false", "blocked", "no", "0"):
        return False
    return None

def as_int(value):
    try:
        return int(str(value).strip())
    except Exception:
        return None

def latest_report(pattern):
    items = sorted(REPORT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return str(items[0]) if items else None

def load_json(path):
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

def extract_first_path(text):
    m = re.search(r"(/root/\.openclaw/workspace/learning-v2/reports/[^\s]+\.json)", text)
    return m.group(1) if m else None

def compact_stdout(result, max_chars=5000):
    out = result.get("stdout") or ""
    err = result.get("stderr") or ""
    text = out
    if err:
        text += "\nSTDERR:\n" + err
    if len(text) > max_chars:
        return text[:max_chars] + "\n...[truncated]..."
    return text

def main():
    generated_at = now_iso()
    ts = stamp()

    git_status = run_cmd(["git", "status", "-sb"])
    git_head = run_cmd(["git", "log", "-1", "--oneline"])

    release_gate = run_cmd(["python3", "scripts/learning-v2-release-gate.py"])
    system_integrity = run_cmd(["python3", "scripts/learning-v2-system-integrity.py"])
    system_preflight = run_cmd(["python3", "scripts/learning-v2-system-preflight.py"])
    local_git_guard = run_cmd(["python3", "scripts/learning-v2-local-git-guard-auditor.py"])
    tamper_guard = run_cmd(["python3", "scripts/learning-v2-tamper-guard.py"])

    release_kv = parse_key_values(release_gate["stdout"])
    integrity_kv = parse_key_values(system_integrity["stdout"])
    preflight_kv = parse_key_values(system_preflight["stdout"])
    guard_kv = parse_key_values(local_git_guard["stdout"])
    tamper_kv = parse_key_values(tamper_guard["stdout"])

    release_report_path = extract_first_path(release_gate["stdout"]) or latest_report("release-gate-*.json")
    integrity_report_path = extract_first_path(system_integrity["stdout"]) or latest_report("system-integrity-*.json")
    preflight_report_path = extract_first_path(system_preflight["stdout"]) or latest_report("system-preflight-*.json")
    guard_report_path = extract_first_path(local_git_guard["stdout"]) or latest_report("local-git-guard-audit-*.json")
    tamper_report_path = extract_first_path(tamper_guard["stdout"]) or latest_report("learning-v2-tamper-guard-*.json")

    mode = release_kv.get("mode") or preflight_kv.get("mode") or integrity_kv.get("mode")
    hard_blocks = release_kv.get("hard_blocks")
    business_source_dirty_count = as_int(
        release_kv.get("business_source_dirty_count")
        or preflight_kv.get("business_source_dirty_count")
        or integrity_kv.get("business_source_dirty_count")
    )

    release_gate_ok = (
        release_gate["returncode"] == 0
        and (hard_blocks in (None, "none", "[]", ""))
    )

    system_integrity_ok = (
        system_integrity["returncode"] == 0
        and integrity_kv.get("system_integrity") == "ok"
    )

    system_preflight_ok = (
        system_preflight["returncode"] == 0
        and preflight_kv.get("system_preflight") == "ok"
    )

    local_git_guard_ok = (
        local_git_guard["returncode"] == 0
        and guard_kv.get("local_git_guard_audit") == "ok"
    )

    tamper_guard_ok = (
        tamper_guard["returncode"] == 0
        and tamper_kv.get("learning_v2_tamper_guard") == "ok"
    )

    ok_for_system_build = as_bool(
        integrity_kv.get("ok_for_system_build")
        or preflight_kv.get("ok_for_system_build")
        or release_kv.get("ok_for_system_build")
    )

    ok_for_commit = as_bool(
        release_kv.get("ok_for_commit")
        or preflight_kv.get("ok_for_commit")
        or integrity_kv.get("ok_for_commit")
    )

    ok_for_deploy = as_bool(
        release_kv.get("ok_for_deploy")
        or preflight_kv.get("ok_for_deploy")
        or integrity_kv.get("ok_for_deploy")
    )

    business_freeze_stable = as_bool(
        release_kv.get("business_freeze_stable")
        or preflight_kv.get("business_freeze_stable")
        or integrity_kv.get("business_freeze_stable")
    )

    dry_run_only = as_bool(
        integrity_kv.get("dry_run_only")
        or preflight_kv.get("dry_run_only")
    )

    business_sources_clean = business_source_dirty_count == 0

    commit_block_expected = (ok_for_commit is False)
    deploy_block_expected = (ok_for_deploy is False)

    learning_v2_health_ok = (
        release_gate_ok
        and system_integrity_ok
        and system_preflight_ok
        and local_git_guard_ok
        and tamper_guard_ok
        and business_sources_clean
        and business_freeze_stable is True
    )

    can_continue_system_build = (
        learning_v2_health_ok
        and ok_for_system_build is True
    )

    next_allowed_actions = []
    if can_continue_system_build:
        next_allowed_actions = [
            "read-only diagnosis",
            "system engineering under learning-v2/",
            "create learning-v2 reports/snapshots",
            "prepare evidence/proposal artifacts",
        ]

    prohibited_actions = [
        "do not commit unless a dedicated gate explicitly allows it",
        "do not push",
        "do not deploy",
        "do not restore Cloudflare production auto-deploy",
        "do not bulk commit unrelated dirty/untracked files",
        "do not modify website business files unless a controlled plan and validation gate explicitly allow it",
    ]

    if learning_v2_health_ok:
        headline = "learning-v2 本体健康。可以继续系统建设；commit/deploy 禁止是当前安全状态，不是错误。"
        status_code = "ok"
        exit_code = 0
    else:
        headline = "learning-v2 当前不应继续推进。请先处理真实阻断项。"
        status_code = "blocked"
        exit_code = 2

    interpretation = {
        "status_code": status_code,
        "headline_zh": headline,
        "learning_v2_health_ok": learning_v2_health_ok,
        "can_continue_system_build": can_continue_system_build,
        "release_gate_ok": release_gate_ok,
        "system_integrity_ok": system_integrity_ok,
        "system_preflight_ok": system_preflight_ok,
        "local_git_guard_ok": local_git_guard_ok,
        "tamper_guard_ok": tamper_guard_ok,
        "mode": mode,
        "hard_blocks": hard_blocks,
        "business_source_dirty_count": business_source_dirty_count,
        "business_sources_clean": business_sources_clean,
        "business_freeze_stable": business_freeze_stable,
        "ok_for_system_build": ok_for_system_build,
        "ok_for_commit": ok_for_commit,
        "ok_for_deploy": ok_for_deploy,
        "dry_run_only": dry_run_only,
        "commit_block_expected": commit_block_expected,
        "deploy_block_expected": deploy_block_expected,
        "commit_false_is_error": False,
        "deploy_false_is_error": False,
        "next_allowed_actions": next_allowed_actions,
        "prohibited_actions": prohibited_actions,
    }

    report = {
        "script_id": SCRIPT_ID,
        "generated_at": generated_at,
        "workspace": str(WORKSPACE),
        "git": {
            "status_sb": git_status["stdout"].strip(),
            "head": git_head["stdout"].strip(),
        },
        "source_reports": {
            "release_gate_report": release_report_path,
            "system_integrity_report": integrity_report_path,
            "system_preflight_report": preflight_report_path,
            "local_git_guard_report": guard_report_path,
            "tamper_guard_report": tamper_report_path,
        },
        "raw_key_values": {
            "release_gate": release_kv,
            "system_integrity": integrity_kv,
            "system_preflight": preflight_kv,
            "local_git_guard": guard_kv,
            "tamper_guard": tamper_kv,
        },
        "interpretation": interpretation,
        "raw_outputs_compact": {
            "release_gate": compact_stdout(release_gate),
            "system_integrity": compact_stdout(system_integrity),
            "system_preflight": compact_stdout(system_preflight),
            "local_git_guard": compact_stdout(local_git_guard),
            "tamper_guard": compact_stdout(tamper_guard),
        },
    }

    report_path = REPORT_DIR / f"learning-v2-agent-status-{ts}.json"
    snapshot_path = SNAPSHOT_DIR / f"learning-v2-agent-status-{ts}.md"

    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = []
    md.append("# Learning V2 Agent Status")
    md.append("")
    md.append(f"- generated_at: {generated_at}")
    md.append(f"- script_id: {SCRIPT_ID}")
    md.append(f"- status_code: {status_code}")
    md.append(f"- headline: {headline}")
    md.append("")
    md.append("## Interpretation")
    md.append("")
    md.append(f"- learning_v2_health_ok: {learning_v2_health_ok}")
    md.append(f"- can_continue_system_build: {can_continue_system_build}")
    md.append(f"- release_gate_ok: {release_gate_ok}")
    md.append(f"- system_integrity_ok: {system_integrity_ok}")
    md.append(f"- system_preflight_ok: {system_preflight_ok}")
    md.append(f"- local_git_guard_ok: {local_git_guard_ok}")
    md.append(f"- tamper_guard_ok: {tamper_guard_ok}")
    md.append(f"- mode: {mode}")
    md.append(f"- hard_blocks: {hard_blocks}")
    md.append(f"- business_source_dirty_count: {business_source_dirty_count}")
    md.append(f"- business_freeze_stable: {business_freeze_stable}")
    md.append(f"- ok_for_system_build: {ok_for_system_build}")
    md.append(f"- ok_for_commit: {ok_for_commit}")
    md.append(f"- ok_for_deploy: {ok_for_deploy}")
    md.append(f"- dry_run_only: {dry_run_only}")
    md.append(f"- commit_block_expected: {commit_block_expected}")
    md.append(f"- deploy_block_expected: {deploy_block_expected}")
    md.append("")
    md.append("## Agent Rule")
    md.append("")
    md.append("- ok_for_commit=false is not an error by itself.")
    md.append("- ok_for_deploy=false is not an error by itself.")
    md.append("- In observe/dry-run modes, commit/deploy blocks are expected safety controls.")
    md.append("- Judge health by system_integrity, system_preflight, release_gate hard_blocks, business_source_dirty_count, and business_freeze_stable.")
    md.append("")
    md.append("## Next Allowed Actions")
    md.append("")
    for item in next_allowed_actions:
        md.append(f"- {item}")
    md.append("")
    md.append("## Prohibited Actions")
    md.append("")
    for item in prohibited_actions:
        md.append(f"- {item}")
    md.append("")
    md.append("## Source Reports")
    md.append("")
    for k, v in report["source_reports"].items():
        md.append(f"- {k}: {v}")
    md.append("")
    md.append("## Git")
    md.append("")
    md.append("```")
    md.append(report["git"]["head"])
    md.append(report["git"]["status_sb"])
    md.append("```")
    md.append("")

    snapshot_path.write_text("\n".join(md), encoding="utf-8")

    print(f"learning_v2_agent_status = {status_code}")
    print(f"headline = {headline}")
    print(f"agent_status_report = {report_path}")
    print(f"agent_status_snapshot = {snapshot_path}")
    print(f"learning_v2_health_ok = {learning_v2_health_ok}")
    print(f"can_continue_system_build = {can_continue_system_build}")
    print(f"tamper_guard_ok = {tamper_guard_ok}")
    print(f"ok_for_commit = {ok_for_commit}")
    print(f"ok_for_deploy = {ok_for_deploy}")
    print(f"commit_block_expected = {commit_block_expected}")
    print(f"deploy_block_expected = {deploy_block_expected}")
    print(f"business_source_dirty_count = {business_source_dirty_count}")
    print("website_files_changed = false")
    print("git_commit = false")
    print("git_push = false")
    print("deploy = false")

    raise SystemExit(exit_code)

if __name__ == "__main__":
    main()
