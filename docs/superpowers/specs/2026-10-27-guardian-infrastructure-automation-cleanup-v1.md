# KYRE GUARDIAN Infrastructure + Automation Cleanup V1

## Intent
Raise infrastructure cleanliness and automation/workflow cleanliness to a trustworthy terminal state without changing sports product behavior.

## Goals
- Remove or neutralize stale scheduled checks that monitor obsolete infrastructure.
- Replace legacy production targets with current authoritative services only where the monitor still has operational value.
- Prevent false-red canary failures on undersized live slates.
- Make Finalizer health truthful: configured services must report configured, missing authority must not look healthy.
- Preserve Guardian isolation from API 2 and MONSTER private state.
- Preserve frozen historical product certifications and sports logic.

## Non-goals
- No sports feature work.
- No provider routing changes.
- No API 2 or MONSTER private ledgers, branches, locks, receipts, or freeze registries.
- No rewriting historical frozen proof artifacts.

## Constraints
- Step 2A: one authoritative branch/PR/run path.
- Anti-Loop: classify root cause before repair; no blind reruns.
- Current Vercel Kyre Sports API is the authoritative live API target for active Guardian production monitoring.
- Historical workflows that have no current operational purpose should be retired rather than cosmetically forced green.
- A one-game slate cannot produce a meaningful 10% or 25% cohort and must not be treated as a production regression.

## Success
Current main/production health is green; active monitors reference current infrastructure; stale schedules cannot create false-red noise; small-slate canaries return a semantic non-failure state; Guardian proof is exact-head green and frozen.