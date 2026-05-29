# BLXST Registry Explicit Apply Policy v0

Purpose: define the final dry-run gate before any real registry update.

This phase is not real apply and not auto-repair.

## Core Law

The explicit apply gate may declare a reviewed apply rehearsal structurally ready for a future controlled apply phase.

It must not write registry files, website source, D1, R2, KV, Workers, Cloudflare, git, or deployment state.

## Rollback Law

Rollback/recovery must be rehearsed before any future real apply.

A ready result only means readiness for a later explicit real-apply phase, not apply now.
