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

## Routing Principle

`/blxst` tasks and authorized Learning V2 system tasks must first identify which resource boundary they touch: Pages, Worker, D1, R2, KV, or a combined path.

## Review Required

- classify 36 observed Workers into production / legacy / test
- fix or document wrangler KV namespace warning
- confirm active role of `news-images-cdn`
- confirm exact CACHE / SESSIONS / CODES namespace mapping

See machine-readable registry: `projects/BLXST-cloudflare-resource-registry.json`
