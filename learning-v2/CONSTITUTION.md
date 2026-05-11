# Learning V2 Constitution

## Entry Rule

Run agent-status before:

- new learning-v2 cycle
- any write or apply step
- baseline decision
- commit decision
- push decision
- deploy decision
- track close

Command:

python3 scripts/learning-v2-agent-status.py

## Reuse Rule

Same task may reuse latest OK status
only if no protected file changed.

## Interpretation Rule

ok_for_commit=false is not an error.
ok_for_deploy=false is not an error.

## Hard Boundary

Do not bypass:

- agent-status
- tamper-guard
- system-integrity
- system-baseline

OpenClaw may use learning-v2.
OpenClaw must not casually modify
learning-v2 core system files.
