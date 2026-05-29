# BLXST Runtime Intake Router Policy v0

Purpose: route runtime intake envelopes to the next dry-run proposal family.

## Core Law

Routing is proposal-only.

It must not write registry, D1, R2, KV, Workers, website source, Cloudflare, git, or deployment state.

## Non-Hardcoded Principle

Routes and priorities are policy-driven and non-exhaustive.

Unknown content routes to review.

## Priority Note

Route priority is policy-driven:

1. Explicit resource/schema requests route before content operations.
2. Concrete media or homepage-copy operations route before generic match/event context.
3. Score/result/standing-oriented match records route before generic event-page requests.
4. Unknown content routes to review.

This is policy guidance, not script hardcoding.
