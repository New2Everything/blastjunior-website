# OpenClaw learning-v2 RUNBOOK v0.9

Scope: learning-v2 self-learning / self-evolution system engineering only.

Current mode:

    system_build_only

Forbidden now:

    website source changes
    git commit
    git push
    deploy

---

## 0. One-command System Preflight

Default first command for system engineering:

    cd /root/.openclaw/workspace
    python3 scripts/learning-v2-system-preflight.py

Expected:

    system_preflight = ok
    steps_ok = True
    ok_for_system_build = True
    ok_for_commit = False
    ok_for_deploy = False
    business_freeze_stable = True
    commit_plan_audit = ok
    business_paths_selected_count = 0
    dry_run_only = True
    commit_now = False
    push_now = False
    deploy_now = False

Meaning:

- system engineering may continue
- website source remains frozen
- commit remains forbidden
- push remains forbidden
- deploy remains forbidden

If preflight fails:

    Do not commit.
    Do not push.
    Do not deploy.
    Read the generated preflight report under learning-v2/reports/.

---

## 1. Current Safety Mode

learning-v2 is currently locked in system_build_only.

Required policy state:

    allow_source_changes = false
    allow_git_commit = false
    allow_deploy = false
    current_topic = None
    current_stage = None

Meaning:

- The self-evolution business cycle is paused.
- No new website source modifications are allowed.
- No commit / push / deploy is allowed.
- System engineering may continue under release gate protection.

---

## 2. Known Frozen Business Dirty State

Current business source dirty files are frozen, not approved.

Frozen business dirty count:

    business_source_blocked_count = 9

Known blocked paths:

    components/nav.css
    components/nav.html
    public/index.html
    public/styles.css
    public/index.html.bak.20260427-105549
    public/styles.css.backup-20260422-064217
    public/styles.css.backup-20260422-064300
    public/styles.css.backup-20260422-064725
    public/styles.css.before-color-fix

Important distinction:

- These files may already be dirty.
- Their current hashes are frozen in learning-v2/freezes/dirty-freeze-*.json.
- They must not change further while system_build_only is active.
- If their hash changes, release gate must fail.

---

## 3. Daily Status Commands

Basic status:

    cd /root/.openclaw/workspace
    python3 scripts/learning-v2-control.py status

Expected:

    learning_v2_status = ok
    current_topic = None
    current_stage = None
    policy_mode = system_build_only
    allow_source_changes = False
    allow_git_commit = False
    allow_deploy = False

Full safety check:

    cd /root/.openclaw/workspace
    python3 scripts/learning-v2-control.py all-safe

Expected:

    doctor_result = ok

Release gate:

    cd /root/.openclaw/workspace
    python3 scripts/learning-v2-release-gate.py

Expected:

    ok_for_system_build = True
    ok_for_commit = False
    ok_for_deploy = False
    business_freeze_stable = True
    hard_blocks = business_source_dirty_exists

This is correct in current mode.

---

## 4. Dirty Freeze Workflow

Create or refresh freeze manifest only intentionally:

    cd /root/.openclaw/workspace
    python3 scripts/learning-v2-dirty-freeze.py

This records the current dirty tree hashes.

Do not refresh the freeze casually. Refreshing the freeze means accepting the current dirty state as the new frozen baseline.

---

## 5. Release Gate Rules

The release gate protects:

1. No active learning-v2 business cycle.
2. Source changes remain disabled.
3. Git commit remains disabled.
4. Deploy remains disabled.
5. Frozen business dirty files have not changed since the last freeze.

Current interpretation:

    ok_for_system_build = True

System scripts/docs may continue.

    ok_for_commit = False
    ok_for_deploy = False

Commit and deploy remain blocked.

---

## 6. What Is Allowed Now

Allowed:

    learning-v2/ system docs
    learning-v2/ reports
    learning-v2/ manifests
    learning-v2/ freezes
    scripts/learning-v2-*.py
    read-only diagnostics
    release gate improvements
    package planning
    commit planning in dry-run mode only

Not allowed:

    public/
    components/
    assets/
    src/
    functions/
    workers/
    git commit
    git push
    Cloudflare deploy

---

## 7. Recommended Next Engineering Steps

Suggested order:

    1. Keep release gate as mandatory first check.
    2. Generate dry-run commit planner.
    3. Generate package manifest for future manual review.
    4. Only later, after explicit approval, decide whether to force-add selected learning-v2 files.

Do not skip release gate.

---

## 8. Emergency Stop

If anything looks wrong:

    cd /root/.openclaw/workspace
    python3 scripts/learning-v2-control.py all-safe
    python3 scripts/learning-v2-release-gate.py
    git status --short

If release gate fails because business source changed:

    Do not commit.
    Do not push.
    Do not deploy.
    Inspect the changed file list from the release gate report.

---

## 9. Current Commit Policy

Current policy:

    commit_allowed = false
    push_allowed = false
    deploy_allowed = false

A future commit planner may be generated, but it must be dry-run only.

No commit command should be executed unless the user explicitly changes policy in a later session.

---

## 10. Local Git Guards

Local Git guards are installed under:

    .git/hooks/pre-commit
    .git/hooks/pre-push

Current expected behavior:

    git commit = blocked
    git push = blocked

Reason:

    system_build_only mode forbids commit / push / deploy.
    Cloudflare Pages may deploy automatically from GitHub main.
    Therefore push must remain blocked while system_build_only is active.

Manual test commands:

    cd /root/.openclaw/workspace
    .git/hooks/pre-commit || true
    .git/hooks/pre-push || true

Expected output:

    [learning-v2 guard] git commit blocked.
    [learning-v2 guard] git push blocked.

The guards call:

    python3 scripts/learning-v2-release-gate.py

They should only allow commit / push in a future explicit unlock mode where release gate reports:

    ok_for_commit = True

For push, release gate must also report:

    ok_for_deploy = True

Current mode does not allow either.

Do not bypass with:

    git commit --no-verify

unless the user explicitly approves a future release procedure.

---

## 11. System Preflight v0.4 Checklist

The one-command preflight now runs 7 checks:

    1. control_all_safe
    2. release_gate_before
    3. commit_planner_dry_run
    4. commit_plan_auditor
    5. local_git_guard_auditor
    6. release_gate_after
    7. control_status

Command:

    cd /root/.openclaw/workspace
    python3 scripts/learning-v2-system-preflight.py

Expected result:

    system_preflight = ok
    steps_total = 7
    steps_ok = True
    ok_for_system_build = True
    ok_for_commit = False
    ok_for_deploy = False
    business_freeze_stable = True
    commit_plan_audit = ok
    business_paths_selected_count = 0
    local_git_guard_audit = ok
    hook_pre-commit_ok = True
    hook_pre-push_ok = True

Interpretation:

    System engineering may continue.
    Website source remains frozen.
    Commit remains blocked.
    Push remains blocked.
    Deploy remains blocked.
    Local Git guards are present and active.

Current first command for any future learning-v2 system work:

    python3 scripts/learning-v2-system-preflight.py

---

## 12. System Baseline Manifest

The system baseline records the current learning-v2 engineering state.

Command:

    cd /root/.openclaw/workspace
    python3 scripts/learning-v2-system-baseline.py

Expected result:

    system_baseline = ok
    business_freeze_stable = True
    ok_for_system_build = True
    ok_for_commit = False
    ok_for_deploy = False
    commit_plan_audit_result = ok
    business_paths_selected_count = 0
    local_git_guard_audit_result = ok

The baseline records:

    learning-v2 system scripts
    learning-v2/RUNBOOK.md
    .git/hooks/pre-commit
    .git/hooks/pre-push
    latest release gate summary
    latest commit plan audit summary
    latest local git guard audit summary
    dirty tree class counts

The baseline is observational only.

It must not:

    git add
    git commit
    git push
    deploy
    change website source

Use baseline when asking:

    Has the learning-v2 system changed since the last known safe state?
    Are all system scripts still present?
    Are local Git guards still present?
    Is business source still frozen?
    Is the current commit plan still dry-run only?

Current rule:

    After editing RUNBOOK or any learning-v2 system script,
    regenerate the baseline.

---

## 13. System Integrity Wrapper

The highest-level one-command check is now:

    cd /root/.openclaw/workspace
    python3 scripts/learning-v2-system-integrity.py

It runs:

    1. system_preflight
    2. policy_lock_audit
    3. mode_policy_audit
    4. system_drift_audit
    5. control_status

Expected result:

    system_integrity = ok
    steps_ok = True
    preflight_result = ok
    policy_lock_audit_result = ok
    mode_policy_audit_result = ok
    drift_audit_result = ok
    drift_count = 0
    ok_for_system_build = True
    ok_for_commit = False
    ok_for_deploy = False
    business_freeze_stable = True
    business_paths_selected_count = 0
    dry_run_only = True

Interpretation:

    learning-v2 system engineering is healthy.
    Policy lock remains engaged.
    Mode Policy v1 is satisfied.
    No system drift was detected.
    Website source remains frozen.
    Commit remains blocked.
    Push remains blocked.
    Deploy remains blocked.

Current recommended first command for any future learning-v2 work:

    python3 scripts/learning-v2-system-integrity.py

After editing RUNBOOK or any learning-v2 system script:

    1. regenerate system baseline
    2. run system integrity

Commands:

    python3 scripts/learning-v2-system-baseline.py
    python3 scripts/learning-v2-system-integrity.py

Do not use integrity success as permission to commit, push, or deploy.
Current system_build_only policy still forbids all release actions.

---

## 14. Handoff Generator

When the conversation window becomes too long, generate a handoff summary.

Command:

    cd /root/.openclaw/workspace
    python3 scripts/learning-v2-handoff.py

Expected result:

    handoff = ok
    recommended_first_command = python3 scripts/learning-v2-system-integrity.py
    system_integrity_result = ok
    policy_lock_audit_result = ok
    mode_policy_audit_result = ok
    mode_policy_current_mode = system_build_only
    drift_count = 0
    business_freeze_stable = True
    ok_for_commit = False
    ok_for_deploy = False

Generated files:

    learning-v2/snapshots/learning-v2-handoff-*.json
    learning-v2/snapshots/learning-v2-handoff-*.md

Use the generated Markdown handoff when starting a new ChatGPT window.

The handoff records:

    current policy mode
    current topic and stage
    latest system integrity result
    latest policy lock audit result
    latest mode policy audit result
    latest system baseline result
    latest drift audit result
    frozen business dirty files
    safe next steps
    hard rules

Hard rules remain:

    do not modify website source
    do not commit
    do not push
    do not deploy
    stay in system_build_only
    keep active cycle paused
    keep policy lock audit green

Recommended future workflow:

    1. Run system integrity.
    2. If healthy, continue system engineering only.
    3. If RUNBOOK or any learning-v2 system script changes, regenerate baseline.
    4. Run system integrity again.
    5. Generate handoff before switching windows.

---

## 15. Mode Policy v1

Mode Policy v1 defines the staged permission model for learning-v2 self-evolution.

Policy file:

    learning-v2/mode-policy.json

Auditor:

    python3 scripts/learning-v2-mode-policy-auditor.py

The four intended modes are:

    1. system_build_only
       System engineering only.
       Active learning cycle must stay paused.
       Topic selector and stage executors are blocked.
       Website source changes are blocked.
       Commit, push, and deploy are blocked.

    2. learning_observe_only
       Learning cycle may run.
       Topic selector may choose learning topics.
       Stage executors may observe, synthesize, and generate proposals.
       Website source changes remain blocked.
       Commit, push, and deploy remain blocked.

    3. source_change_allowed
       Source changes may occur only inside an explicitly approved scope.
       Commit, push, and deploy remain blocked.

    4. release_allowed
       Reserved for future manual unlock only.
       Requires explicit scope, release plan, rollback plan, and manual approval.

Current required state for system_build_only:

    system_build_only = True
    current_topic = None
    current_stage = None
    current_target_family = None
    allow_source_changes = False
    allow_git_commit = False
    allow_deploy = False

The highest-level integrity wrapper now includes mode policy audit:

    python3 scripts/learning-v2-system-integrity.py

Expected healthy result:

    system_integrity = ok
    policy_lock_audit_result = ok
    mode_policy_audit_result = ok
    drift_count = 0

Do not switch to learning_observe_only until system_integrity is green and the user explicitly asks to restore the learning cycle.
