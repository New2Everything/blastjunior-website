# BLXST Cloudflare Resource Registry v0

Purpose: bind BLXST / Learning V2 to real Cloudflare resource boundaries so OpenClaw direct commands and Learning V2 autonomous cycles do not conflict.

## Deployment Law

- `push != deploy`
- `production_deployments_enabled` must remain `false`
- production publishing must use Learning V2 controlled Cloudflare Pages deploy

## Core Resources

- Pages: `blastjunior-website` → `blastjunior.com` / `www.blastjunior.com`
- GitHub: `New2Everything/blastjunior-website` on `main`
- Primary Worker: `blast-homepage-api`
- Core D1: `blast-campaigns-db`, `blast-user-db`, `blast-photo-db`, `news-database`
- Core R2: `blastjunior-media`
- Observed KV: `blast-cache`, `blast-comments`, `blastjunior-registrations`, `blast-photo-meta`, `blast-safe-logs`, `blast-subscriptions`, `blast-upload-queue`


## Data Provenance Law

The system may improve data structures and may add content into those structures, but every content record must carry provenance.

Allowed source types:

- `human_provided`: directly provided by OldK or submitted by real website users.
- `ai_researched_or_distilled`: AI searched, processed, summarized, or structured from real-world evidence; must be marked and linked to evidence/source references.
- `ai_generated_marked`: rare explicitly synthetic content, clearly marked as AI-generated, such as an AI admin identity.

Forbidden:

- AI must not invent fake match records.
- AI must not invent fake news.
- AI must not invent fake event types and present them as real.
- AI must not invent fake club logos or real-world brand assets.
- AI must not create unmarked synthetic production data.

Default rule: unclear provenance means draft/review-only, not publishable.


## Routing Principle

`/blxst` tasks and authorized Learning V2 system tasks must first identify which resource boundary they touch: Pages, Worker, D1, R2, KV, or a combined path.

## Review Required

- classify 36 observed Workers into production / legacy / test
- fix or document wrangler KV namespace warning
- confirm active role of `news-images-cdn`
- confirm exact CACHE / SESSIONS / CODES namespace mapping

See machine-readable registry: `projects/BLXST-cloudflare-resource-registry.json`
