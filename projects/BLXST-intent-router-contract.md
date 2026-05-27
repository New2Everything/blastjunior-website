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
