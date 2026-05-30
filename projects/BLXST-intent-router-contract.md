# BLXST Intent Router Contract

## Purpose

OpenClaw is the direct instruction entry point. Learning V2 is the resource classifier, safety gate, deployment controller, audit layer, and self-learning optimizer.

Not every OpenClaw conversation is a website task. Before entering Learning V2, every user instruction must be classified.

## Direct Command Prefix

The only recommended direct command prefix is:

`/blxst`

Meaning:

- The user is explicitly telling OpenClaw this task is related to the BLXST website, data library, media assets, match records, event pages, Cloudflare resources, or production publishing.
- OpenClaw must route the task into the Intent Router.
- Learning V2 must then classify the resource boundary and choose the correct controlled pipeline.
- Ordinary non-website tasks do not need this prefix.

Examples:

- `/blxst update the homepage slogan`
- `/blxst archive these match records into the event page`
- `/blxst upload these photos to the correct gallery/event resource`
- `/blxst publish the confirmed website update through controlled deploy`

If `/blxst` is absent, OpenClaw should treat the message as a normal task unless the content is clearly website/resource/deploy related. If uncertain, ask a clarification or analyze only.

## Top-Level Routing

1. Non-website task
   - handled by OpenClaw normally
   - does not enter Learning V2 website pipeline

2. Website content task
   - enters Learning V2 controlled pipeline
   - examples: update website slogan, news, photos, event page, match record

3. Website data task
   - enters resource gate
   - examples: teams, players, standings, registrations, seasons, campaigns, match records

4. Media resource task
   - enters R2/media gate
   - examples: upload photos, gallery media, thumbnails, event images

5. Worker/API task
   - enters Worker/API gate
   - examples: login, registration, upload review, homepage API, CORS, auth, online presence

6. Deployment task
   - enters controlled Pages deploy gate
   - push is not deploy
   - production auto-deploy must remain disabled unless a separate phase explicitly changes it

7. Mixed task
   - split into ordinary OpenClaw task plus Learning V2 website/resource task

8. Uncertain task
   - ask a clarification or perform analysis only
   - do not mutate website resources


## Authorized Intent Context Guard

`/blxst` is the only recommended prefix for user-direct BLXST tasks, but it is not the only legal Learning V2 entry source.

Valid authorized intent contexts include:

- `user_direct_with_/blxst`
- `user_confirmed_blxst_after_prompt`
- `scheduled_learning_task`
- `autonomous_learning_cycle`
- `controlled_deploy_phase`
- `maintenance_observer`

Rules:

- A normal OpenClaw conversation without `/blxst` should not mutate BLXST website resources.
- Scheduled tasks and autonomous Learning V2 cycles do not require `/blxst`, but they must carry task origin, target project, mode, scope, and gate context.
- Write, commit, push, and deploy require authorized context plus mode policy plus the relevant gate chain.
- Reuse existing Learning V2 control layers before creating a new controller.

Reuse priority:

- `mode_policy_auditor`
- `control_status`
- `mode_transition_checker`
- `release_gate`
- `source_change_gate`
- `push_deploy_safety_gate`
- `deployment_route_contract`
- `push_approval_gate`


## Content Provenance Rule

Learning V2 may help complete structures and content, but it must mark content source.

Content may be:

- `human_provided`
- `ai_researched_or_distilled`
- `ai_generated_marked`

Unmarked AI-generated real-world content is forbidden. The system must not fabricate, misrepresent, or publish unverified real-world content, factual content, production data, event data, organization/brand/person data, media assets, or operational facts. Any examples are illustrative and non-exhaustive.



## Resource Classification Step

Every `/blxst` task and every authorized Learning V2 system task must run resource classification before any mutation.

Classifier:

`python3 scripts/learning-v2-resource-classifier.py --origin <authorized_context> --text "<task text>"`

The classifier is dry-run only. It may read the Cloudflare Resource Registry and write reports, but it must not mutate website source, D1, R2, KV, Workers, Cloudflare Pages, git, or deployment state.

Classification output must identify touched resource boundaries such as:

- Pages/static source
- Cloudflare Pages controlled deploy
- Worker/API
- D1 databases
- R2 buckets
- KV namespaces
- ordinary or uncertain task

A task may proceed to later gates only after its resource boundary is known.

Examples:

- match records → `blast-campaigns-db` plus page generation
- website photos → `blastjunior-media` plus photo metadata
- homepage slogan → Pages/static source or content config
- login/register/session → Worker/API plus `blast-user-db` plus KV/session gate
- publish confirmed update → controlled Pages deploy gate
- normal analysis without authorized context → ordinary task or read-only classification only



## Resource Classifier Extensibility Law

The resource classifier must not become a fixed hardcoded resource list.

Version v0 may use seed rules for known BLXST resources, but the long-term classifier must be registry-driven and extensible.

Required behavior:

- Read Cloudflare Resource Registry as the source of truth for Pages, Workers, D1, R2, KV, and future resources.
- Treat hardcoded mappings only as seed hints, not as complete truth.
- If Learning V2 later adds a D1 database, D1 table, R2 bucket, KV namespace, Worker, API route, page structure, or content structure, the classifier must be able to learn it through registry updates or routing-rule updates.
- Unknown or newly discovered resources must not be ignored.
- Unknown resources must be classified as `unknown_resource_boundary`, `registry_update_required`, or `review_required`.
- The classifier must prefer a safe “needs review” result over a false confident result.
- Adding resources should normally update registry/routing rules before changing classifier code.

This prevents the classifier from breaking when the system self-evolves.



## Gate Policy Registry Step

After resource classification, Learning V2 must consult the Gate Policy Registry before any mutation.

Gate policy must be registry-driven and extensible. It must not freeze current D1, R2, KV, Worker, Pages, or content structures into a hardcoded list.

The policy registry may provide non-exhaustive seed hints, but exact behavior must come from registry/routing rules, authorized context, provenance requirements, risk, operation intent, and current mode.

Unknown/new resources must route to `registry_update_required` and `review_required`.



## Gate Plan Dry Run Step

After resource classification and gate policy lookup, Learning V2 should produce a gate plan dry-run before any mutation.

Gate plan dry-run:

`python3 scripts/learning-v2-gate-plan-dry-run.py --origin <authorized_context> --text "<task text>"`

The gate plan reads classifier output and the Gate Policy Registry, then recommends gate families without mutating website source, D1, R2, KV, Workers, Cloudflare, git, or deployment state.

The gate plan must remain policy-driven and registry-driven. Seed hints are not complete truth.

Unknown/new resources must result in `registry_update_required` or `review_required` before later stages.



## Autonomous Path Rehearsal Step

Before claiming Learning V2 can run without human repair, the system must pass autonomous path rehearsal.

Rehearsal script:

`python3 scripts/learning-v2-autonomous-path-rehearsal.py`

This rehearsal verifies that representative authorized, unknown-resource, ordinary, and controlled-deploy-phase tasks can reach a machine-readable gate plan or safe-stop state without mutating website source, D1, R2, KV, Workers, Cloudflare, git, or deployment state.

Passing this rehearsal proves the autonomous planning path, not production mutation. Real D1/R2/Worker writes, autonomous source writes, controlled deploy, rollback, and production recovery require separate later rehearsals.



## Failure Context Resolver Step

When any stage is blocked, review-required, no-auth, unknown-resource, or ambiguous, Learning V2 must produce a machine-readable failure context before asking for repair.

Resolver:

`python3 scripts/learning-v2-failure-context-resolver.py --latest gate_plan`

The resolver must output resolved status, safe-stop status, whether continuation is allowed, next action families, and mutation safety flags.

The resolver is diagnostic-only, not an auto-repair tool. It must not mutate website source, D1, R2, KV, Workers, Cloudflare, git, or deployment state.

Status families are policy families and non-exhaustive. Unknown or future failure states must default to `safe_stop_failure_triage_required`, `triage_unknown_state`, and `do_not_mutate`.



## Autonomous Next-Action Dispatcher Step

After Failure Context Resolver, Learning V2 may run the autonomous next-action dispatcher.

Dispatcher:

`python3 scripts/learning-v2-autonomous-next-action-dispatcher.py`

The dispatcher reads resolver output and `projects/BLXST-next-action-dispatcher-policy.json`, then recommends the next safe dry-run, review, registry update, authorization request, or triage action.

The dispatcher is recommendation-only, not auto-repair. It must not mutate website source, D1, R2, KV, Workers, Cloudflare, git, or deployment state.

Unknown next-action families must route to `triage_unknown_state` and `do_not_mutate`.



## Next-Action Dry-run Handler Step

After Autonomous Next-Action Dispatcher, Learning V2 may run the next-action dry-run handler.

Handler:

`python3 scripts/learning-v2-next-action-dry-run-handler.py`

The handler turns selected_next_action into a proposal or report only. It is not auto-repair.

Examples include registry update proposal, review gate report, authorization request, failure triage report, unknown-state triage report, or rerun recommendation.

The handler must not write registry, website source, D1, R2, KV, Workers, Cloudflare, git, or deployment state.



## Registry Update Proposal Dry-run Step

When the next-action handler selects `update_resource_registry`, Learning V2 may create a registry update proposal dry-run.

Proposal script:

`python3 scripts/learning-v2-registry-update-proposal-dry-run.py`

The proposal may identify candidate registry, routing-rule, or gate-policy updates, but it must not write registry files or mutate Cloudflare, D1, R2, KV, Workers, git, or deployment state.

Registry update apply requires a separate later rehearsal.



## Registry Update Proposal Review Gate Step

After Registry Update Proposal Dry-run, Learning V2 may run the registry update proposal review gate.

Review gate:

`python3 scripts/learning-v2-registry-update-proposal-review-gate.py`

The review gate may decide whether a registry update proposal is structurally ready for a later apply rehearsal, but it must not approve real mutation or write registry files.

A ready review result allows only a future apply rehearsal, not production apply.



## Registry Update Apply Rehearsal Step

After Registry Update Proposal Review Gate returns `apply_rehearsal_allowed=true`, Learning V2 may run registry update apply rehearsal.

Apply rehearsal:

`python3 scripts/learning-v2-registry-update-apply-rehearsal.py`

This rehearsal drafts an apply manifest, validation plan, and rollback/recovery note, but must not write registry files or mutate website source, D1, R2, KV, Workers, Cloudflare, git, or deployment state.

A successful apply rehearsal allows only a later explicit apply gate, not real apply.



## Registry Explicit Apply Gate and Rollback Rehearsal Step

After Registry Update Apply Rehearsal, Learning V2 may run explicit apply gate dry-run and rollback rehearsal.

Scripts:

`python3 scripts/learning-v2-registry-update-explicit-apply-gate.py`

`python3 scripts/learning-v2-registry-update-rollback-rehearsal.py`

`python3 scripts/learning-v2-registry-chain-readiness-matrix.py`

These scripts may declare readiness for a later controlled apply context, but must not write registry files or mutate website source, D1, R2, KV, Workers, Cloudflare, git, or deployment state.

A ready matrix does not allow real apply now.



## Autonomous E2E Dry-run Orchestrator Step

Learning V2 may run the autonomous E2E dry-run orchestrator to connect task text through gate plan, failure resolver, dispatcher, next-action handler, registry proposal/review/apply rehearsal, and explicit apply gate when applicable.

Orchestrator:

`python3 scripts/learning-v2-autonomous-e2e-dry-run-orchestrator.py --origin <authorized_context> --text "<task text>"`

The orchestrator follows report outputs and policy decisions. It must not hardcode future resource names, and must not mutate registry files, website source, D1, R2, KV, Workers, Cloudflare, git, or deployment state.

A ready result means readiness for a later controlled context, not real apply now.



## Controlled Apply Context Gate and Disabled Executor Step

After Autonomous E2E Dry-run Orchestrator returns readiness for a later controlled context, Learning V2 may run controlled apply context gate and disabled executor skeleton.

Scripts:

`python3 scripts/learning-v2-controlled-apply-context-gate.py`

`python3 scripts/learning-v2-registry-controlled-apply-executor.py`

`python3 scripts/learning-v2-controlled-apply-readiness-smoke.py`

The context gate validates explicit controlled apply context. The executor skeleton is disabled in this phase and must refuse real apply. These scripts must not write registry files or mutate website source, D1, R2, KV, Workers, Cloudflare, git, or deployment state.

A passing readiness smoke means the future apply path is guarded, not that real apply is allowed now.



## Runtime Entrypoint and Launch Readiness Auditor Step

OpenClaw may call Learning V2 through the runtime dry-run entrypoint:

`python3 scripts/learning-v2-runtime-entrypoint-dry-run.py --origin <authorized_context> --text "<task text>"`

Learning V2 may summarize launch readiness through:

`python3 scripts/learning-v2-launch-readiness-auditor.py`

These scripts provide a single dry-run runtime path and readiness summary. They must not mutate registry files, website source, D1, R2, KV, Workers, Cloudflare, git, or deployment state.

Runtime dry-run readiness does not mean production mutation or production deploy readiness.



## Runtime Origin Policy and OpenClaw Bridge Step

Learning V2 runtime origins must be read from `projects/BLXST-runtime-origin-policy.json`, not hardcoded in scripts.

OpenClaw may call the bridge dry-run:

`python3 scripts/learning-v2-openclaw-blxst-bridge-dry-run.py --text "/blxst ..."`

The bridge infers `/blxst` user-direct tasks and forwards them to the runtime entrypoint. Unknown origins safe-stop before mutation.

This bridge is dry-run only and must not mutate registry files, website source, D1, R2, KV, Workers, Cloudflare, git, or deployment state.



## Runtime Intake Envelope and Provenance Staging Step

Before user/OpenClaw BLXST content is written anywhere, Learning V2 may create a runtime intake envelope:

`python3 scripts/learning-v2-runtime-intake-envelope-dry-run.py --origin <authorized_context> --text "<content>"`

The intake envelope records source type, content hash, content family candidates, provenance note, review status, and recommended next family.

It must not mutate registry files, website source, D1, R2, KV, Workers, Cloudflare, git, or deployment state.

User-submitted content is evidence of submission, not automatic publication approval.



## Runtime Intake Router Step

After Runtime Intake Envelope, Learning V2 may route the intake envelope to the next dry-run proposal family:

`python3 scripts/learning-v2-runtime-intake-router-dry-run.py --origin <authorized_context> --text "<content>"`

The router maps policy-driven content family candidates to proposal routes such as structured data/event page proposal, media staging proposal, source copy proposal, registry update proposal, or review gate.

It must not mutate registry files, website source, D1, R2, KV, Workers, Cloudflare, git, or deployment state.

Routes are non-exhaustive and policy-driven.



## Content Proposal Factory Step

After Runtime Intake Router, Learning V2 may create a content proposal:

`python3 scripts/learning-v2-content-proposal-factory-dry-run.py --origin <authorized_context> --text "<content>"`

The factory turns selected routes into proposal shapes for event data/pages, media staging, homepage copy changes, registry handoff, or review.

It must not mutate registry files, website source, D1, R2, KV, Workers, Cloudflare, git, or deployment state.

Content proposals remain review-required before any apply or publish step.



## Content Proposal Review Gate and Apply Rehearsal Step

After Content Proposal Factory, Learning V2 may run content proposal review gate and content apply rehearsal dry-run:

`python3 scripts/learning-v2-content-proposal-review-gate.py --origin <authorized_context> --text "<content>"`

`python3 scripts/learning-v2-content-apply-rehearsal-dry-run.py --origin <authorized_context> --text "<content>"`

Review gate may allow apply rehearsal only. Apply rehearsal drafts a plan only.

These scripts must not mutate registry files, website source, D1, R2, KV, Workers, Cloudflare, git, or deployment state.

A ready rehearsal does not allow real apply or production deploy.



## Content Controlled Apply Context Gate and Disabled Executor Step

After Content Apply Rehearsal, Learning V2 may run content controlled apply context gate and disabled executor skeleton:

`python3 scripts/learning-v2-content-controlled-apply-context-gate.py`

`python3 scripts/learning-v2-content-controlled-apply-executor.py`

`python3 scripts/learning-v2-content-controlled-apply-readiness-smoke.py`

The context gate validates explicit controlled content apply context. The executor skeleton is disabled in this phase and must refuse real apply.

These scripts must not mutate registry files, website source, D1, R2, KV, Workers, Cloudflare, git, or deployment state.

A passing readiness smoke means the future content apply path is guarded, not that real apply is allowed now.



## Content Runtime E2E Orchestrator Step

Learning V2 may run the content runtime E2E dry-run orchestrator:

`python3 scripts/learning-v2-content-runtime-e2e-dry-run-orchestrator.py --origin <authorized_context> --text "<content>"`

The orchestrator connects content apply rehearsal, content controlled apply context gate, and disabled executor when applicable.

It must not mutate registry files, website source, D1, R2, KV, Workers, Cloudflare, git, or deployment state.

A guarded E2E result means the future controlled content apply path is protected, not that real apply or production deploy is allowed now.


## Cloudflare Resource Boundaries

The router must identify whether a task touches:

- Cloudflare Pages: blastjunior-website
- production domain: blastjunior.com
- GitHub repo: New2Everything/blastjunior-website
- branch: main
- Workers: blast-homepage-api and other business APIs
- D1: structured website data such as campaigns, teams, players, news, registrations, standings, match records
- R2: media files, photos, thumbnails, gallery assets
- KV: sessions, cache, presence, state

## Unified Pipeline

User-driven website updates and Learning V2 self-discovered website improvements must converge into the same pipeline:

intent classification
→ resource boundary detection
→ data/resource write
→ page generation or update
→ validation
→ commit
→ push
→ controlled deploy
→ live verification
→ outcome record
→ future self-learning optimization

## Legacy Rule

The old model `push main = production deploy` is legacy and invalid.

Current law:

push != deploy

Production release must use Learning V2 controlled deployment.
