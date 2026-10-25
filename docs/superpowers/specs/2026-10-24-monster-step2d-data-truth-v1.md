# MONSTER Step 2D Data-Truth + Zero-False-Blank V1

## Intent
Make MONSTER independently prove that data survives its authoritative path without technical failures becoming false absence states, false blanks, cached negatives, or fabricated values.

## System boundary
This is MONSTER-only. The shared repository is allowed, but foreign-system branches, PRs, runs, deployments, leases, locks, checkpoints, ledgers, proof artifacts, recovery state, authorization tokens, evidence, and GREEN/FROZEN state are never accepted as MONSTER authority or evidence.

## Mandatory lifecycle
FAILURE -> ANTI-LOOP -> STEP 2C -> STEP 2B -> STEP 2A -> EXECUTE -> STEP 2D -> VERIFY -> GREEN -> FROZEN.

Step 2D runs only after a completed MONSTER execution receipt and before final verification authorization.

## Step 2D data path
For each field, prove:
SOURCE -> INGESTION -> PARSER -> IDENTIFICATION/MAPPING -> NORMALIZATION -> MONSTER AUTHORITATIVE DATA PATH -> CONSUMER -> FINAL OUTPUT.

## Truth rules
1. Empty is not proof of absence.
2. Technical failures remain explicit: PROVIDER_FETCH_FAILURE, PARSER_FAILURE, EVENT_MAPPING_FAILURE, ENTITY_MAPPING_FAILURE, MARKET_MAPPING_FAILURE, STALE_DATA, SOURCE_CONFLICT, ALL_SOURCES_UNAVAILABLE.
3. Absence requires successful path proof plus a fingerprinted verified-absence record.
4. Fallbacks must be field-specific, approved, selected for a stated reason, and never blind fan-out.
5. Missing data is never replaced with invented values.
6. Technical failures may never write negative-cache absence entries.
7. When a value exists, source truth, MONSTER authoritative truth, and final-output truth must match semantically.
8. A legitimate zero is data when the source truth is zero; zero is not treated as blank.
9. Any Step 2D failure preserves evidence and routes to MONSTER Anti-Loop -> Step 2C rather than authorizing final verification.

## Completion contract
GREEN requires the MONSTER-owned Anti-Loop, Step 2A, Step 2B, Step 2C, Step 2D, exact-head workflow, regression suite, and final state readback to pass. FROZEN additionally requires merge, post-merge proof, a MONSTER-owned frozen record, and readback with matching hashes/identifiers.
