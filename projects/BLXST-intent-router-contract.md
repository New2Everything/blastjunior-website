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
