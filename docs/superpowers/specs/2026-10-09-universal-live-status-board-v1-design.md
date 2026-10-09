# Universal Live Status Board V1 — Design Spec

## Purpose

Create one shared, machine-checkable status contract for this chat, MONSTER, and API 2 so every execution update always shows:

1. completion percentage,
2. RED / YELLOW / GREEN state,
3. the live active chat.

The system must reduce ambiguity, cross-chat overlap, invisible stalls, and manual rescue prompts without creating a second ownership system that competes with the existing Step 2A / scope-aware execution lease control plane.

## Scope

This design is a four-step control-plane upgrade:

1. Mandatory Status Schema
2. Authoritative Chat Ownership Registry
3. Heartbeat + Stale-Owner Recovery
4. Enforcement Gate

Step 1 is implemented first and frozen before Step 2 begins.

## Existing Systems Reused

The design must reuse, not replace:

- `devsystem/scope_aware_execution_lease_v1.py`
- existing scope-aware lease state on `monster-scope-aware-execution-leases`
- cross-workstream arbitration / shared-resource lease machinery
- Step 2A authority rules
- Runless exact-head proof / terminal receipts
- frozen-artifact registry and transactional freeze

No duplicate mutation-ownership registry may be introduced in Step 1.

## Step 1 — Mandatory Status Schema

### Required fields

Every valid execution status packet must contain:

- `completion_percent`
  - numeric
  - inclusive range `0.0` through `100.0`

- `status`
  - enum: `RED`, `YELLOW`, `GREEN`

- `live_active_chat`
  - enum: `THIS_CHAT`, `MONSTER`, `API_2`, `NONE_TERMINAL`

These are the three user-mandated fields. Omitting any of them is a validation failure.

### Support fields

Each packet may also contain:

- `frozen`: boolean, required by terminal validation
- `current_blocker`: string or null
- `next_legal_action`: string or null
- `current_step`: string or null
- `overall_progress_percent`: numeric or null
- `authoritative_owner`: string or null
- `scope_lease_id`: string or null

### Semantic rules

- `RED`
  - execution is blocked or failed
  - `current_blocker` must be non-empty
  - `next_legal_action` should identify the reconciliation action when known

- `YELLOW`
  - work is actively executing, waiting on one authoritative result, or not yet terminal
  - `frozen` must be false

- `GREEN`
  - required proof for the represented checkpoint is satisfied
  - `completion_percent` may be below 100 for a completed sub-step inside a larger program, but terminal freeze rules still apply to the represented task

- `GREEN + FROZEN`
  - represented as `status=GREEN`, `completion_percent=100`, `frozen=true`
  - this is the terminal task state

### Invariants

- `completion_percent < 0` or `> 100` is invalid.
- `completion_percent == 100` requires `status == GREEN`.
- `frozen == true` requires:
  - `status == GREEN`
  - `completion_percent == 100`
- `live_active_chat == NONE_TERMINAL` requires terminal state:
  - `status == GREEN`
  - `completion_percent == 100`
  - `frozen == true`
- `RED` requires a non-empty `current_blocker`.
- A missing mandatory field is always invalid.
- Unknown status or chat values are invalid.

## Step 1 Output Contract

Step 1 will provide:

1. a pure validator that accepts a status packet and either returns a normalized packet or fails closed;
2. a deterministic renderer for the visible control-room board;
3. tests covering all required invariants and invalid states;
4. a Runless proof plan for exact-head certification;
5. a task ledger and execution plan;
6. a frozen-registry entry after exact-head merge and post-merge proof reuse.

The Step-1 validator must be side-effect free:

- no network calls,
- no product/runtime mutation,
- no lease acquisition,
- no chat ownership mutation,
- no GitHub Actions fallback.

## Visible Board Format

A normalized visible board should render at minimum:

```text
UNIVERSAL LIVE STATUS BOARD
Completion: 87%
Status: YELLOW
Live Active Chat: API_2
Current Blocker: production SHA convergence
Next Legal Action: consume authoritative deployment result
```

Terminal example:

```text
UNIVERSAL LIVE STATUS BOARD
Completion: 100%
Status: GREEN + FROZEN
Live Active Chat: NONE_TERMINAL
Current Blocker: none
Next Legal Action: none
```

The renderer may decorate RED/YELLOW/GREEN with emoji for chat display, but the machine contract remains the canonical enum values.

## Step 2 — Authoritative Chat Ownership Registry

Step 2 will bind `live_active_chat` to existing authoritative lease/control-plane truth rather than memory or manual labeling.

It must:

- read the existing scope-aware execution lease state,
- map a current workstream owner to `THIS_CHAT`, `MONSTER`, or `API_2`,
- fail closed on ambiguous ownership,
- avoid creating a parallel mutation-authority system,
- preserve cross-chat state separation.

Step 2 is explicitly out of scope for Step 1 implementation.

## Step 3 — Heartbeat + Stale-Owner Recovery

Step 3 will make the visible active-chat state self-correcting when an execution owner expires or becomes stale.

It will reuse existing lease heartbeat / dead-man / event-driven recovery mechanisms where possible.

Step 3 is explicitly out of scope for Step 1 implementation.

## Step 4 — Enforcement Gate

Step 4 will make the status board mandatory for execution updates. An execution update missing the Step-1 contract will fail validation before it can be treated as an authoritative control-room update.

Step 4 is explicitly out of scope for Step 1 implementation.

## Step 1 TDD Acceptance Cases

At minimum, tests must prove:

1. a valid YELLOW active packet passes;
2. a valid RED packet with blocker passes;
3. RED without blocker fails;
4. valid GREEN 100% + frozen passes;
5. 100% with YELLOW fails;
6. frozen with less than 100% fails;
7. frozen with RED or YELLOW fails;
8. `NONE_TERMINAL` before terminal state fails;
9. missing `completion_percent` fails;
10. missing `status` fails;
11. missing `live_active_chat` fails;
12. unknown status fails;
13. unknown chat fails;
14. percentage outside `[0,100]` fails;
15. deterministic rendering is stable for identical normalized input;
16. renderer displays all three mandatory user fields;
17. module grants no network/product/ambient mutation authority.

## Step 1 Proof and Finalization

Step 1 uses the normal execution kernel:

Problem → Root Cause → Patch → Proof/Test → GREEN → Freeze → Next

Required closeout:

1. Step 2A exact scope reconciliation
2. TDD RED
3. minimal implementation
4. targeted regression proof
5. exact-head Runless certification
6. one PR maximum
7. exact-head merge
8. deterministic post-merge proof reuse
9. transactional frozen-registry update
10. independent registry read-back
11. Step-1 freeze token confirmed
12. release authority

GitHub Actions fallback remains `0` unless the user explicitly authorizes emergency fallback.

## Proposed Step 1 Freeze Token

`UNIVERSAL_LIVE_STATUS_BOARD_V1_STEP1_MANDATORY_STATUS_SCHEMA_FROZEN`

The exact token is fixed by this spec unless changed before implementation-plan approval.

## Non-Goals

Step 1 does not:

- infer chat ownership from memory;
- acquire or transfer mutation authority;
- stop API 2 from working independently on non-overlapping scope;
- replace Step 2A;
- replace Runless;
- replace the frozen registry;
- modify sports product/runtime/model/projection logic;
- create background scheduling or continuous autonomous execution outside available execution mechanisms.

## Success Criteria

Step 1 is complete only when the mandatory schema is independently proven and frozen. After Step 1, every future Universal Live Status packet has a single canonical answer for:

- how complete the represented task is,
- whether it is RED, YELLOW, or GREEN,
- which chat is identified as live/active by the packet.

Ownership truth itself becomes authoritative in Step 2.
