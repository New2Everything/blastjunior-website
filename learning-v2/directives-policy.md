# Learning V2 Directives Policy

## Purpose

This file records durable user directives that should guide learning-v2 behavior without requiring the raw directives inbox queue to be committed.

The raw queue remains local state unless a separate policy later decides otherwise.

## Source

This policy is distilled from:

- learning-v2/inbox/directives-inbox.jsonl

It intentionally preserves durable intent, not raw queue mechanics.

## Policy Rules

### DP-001: User Directives Outrank AI Inference

User direct requirements must outrank AI inference.

When the user's explicit instruction conflicts with an AI-generated assumption, optimization path, or inferred direction, the user's explicit instruction wins.

Operational meaning:

- Do not let AI inference override direct user requirements.
- When uncertain, choose the smaller, safer, more reversible action.
- Prefer less-is-more execution unless the user explicitly asks for expansion.

### DP-002: Do Not Optimize Around Booking or Join-Club CTA Flows

Do not continue learning, proposing, or optimizing the club website around booking-experience or join-club CTA flows unless the user explicitly re-opens that direction.

Operational meaning:

- Do not treat booking-experience as the default conversion path.
- Do not treat join-club CTA as the default website improvement path.
- Avoid repeatedly rediscovering this direction as a new learning target.
- Return to topic learning and user-approved priorities instead.

## Raw Queue Handling

- `learning-v2/inbox/directives-inbox.jsonl` remains a raw local queue for now.
- Do not commit the raw queue until repository privacy and queue lifecycle policy are decided.
- Do not hide or archive the raw queue until this tracked policy summary is reviewed and accepted.
- Future raw directives should either be reviewed into this policy or explicitly archived as obsolete local evidence.

## Safety

This policy does not permit:

- source writes
- git add
- git commit
- git push
- deploy
- production route changes

All operational changes still require the normal learning-v2 gates.
