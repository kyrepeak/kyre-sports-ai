# Universal Live Status Board V1 Step 1 — Mandatory Status Schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and freeze a pure, machine-checkable status-board contract that always exposes completion percentage, RED/YELLOW/GREEN state, and the live active chat.

**Architecture:** Add one side-effect-free DevSystem module responsible only for validating and rendering status packets. Keep ownership resolution out of Step 1; Step 2 will bind `live_active_chat` to existing lease truth. Step 1 ships with focused TDD, Runless exact-head proof, one PR maximum, deterministic post-merge reuse, and transactional freeze.

**Tech Stack:** Python 3, pytest, DevSystem JSON execution/runless/task-ledger conventions, existing Runless proof plane, existing frozen-artifact registry.

**Spec:** `docs/superpowers/specs/2026-10-09-universal-live-status-board-v1-design.md`

## Global Constraints

- The three mandatory fields are exactly `completion_percent`, `status`, and `live_active_chat`.
- `status` enum is exactly `RED`, `YELLOW`, `GREEN`.
- `live_active_chat` enum is exactly `THIS_CHAT`, `MONSTER`, `API_2`, `NONE_TERMINAL`.
- `completion_percent` must be numeric and within inclusive range `0.0..100.0`.
- `completion_percent == 100` requires `status == GREEN`.
- `frozen == true` requires `status == GREEN` and `completion_percent == 100`.
- `live_active_chat == NONE_TERMINAL` requires terminal GREEN + 100 + frozen state.
- `RED` requires a non-empty `current_blocker`.
- Step 1 must not acquire/transfer authority or infer ownership from memory.
- Step 1 must make no network calls and no product/runtime/model mutations.
- Reuse existing Step 2A, Runless, scope-aware lease, and frozen-registry systems; do not create a parallel ownership registry.
- GitHub Actions fallback remains `0` unless the user explicitly authorizes emergency fallback.
- Freeze token: `UNIVERSAL_LIVE_STATUS_BOARD_V1_STEP1_MANDATORY_STATUS_SCHEMA_FROZEN`.

## Review Focus

- Python `bool` values passed as `completion_percent` must be rejected even though `bool` subclasses `int`.
- `NaN` or infinite completion percentages must fail closed instead of passing numeric range checks.
- Whitespace-only RED blockers must be treated as missing blockers.
- Renderer output must not vary with dictionary insertion order.
- Terminal packets must not silently retain a non-terminal active chat value when `frozen=true` and `completion_percent=100`.

---

### Task 1: Pure Status Packet Validator + Deterministic Renderer

**Files:**
- Create: `devsystem/universal_live_status_board_v1.py`
- Create: `tests/test_devsystem_universal_live_status_board_v1.py`

**Interfaces:**
- Consumes: a `Mapping[str, Any]` status packet supplied by callers.
- Produces: `validate_status_packet(packet: Mapping[str, Any]) -> dict[str, Any]`.
- Produces: `render_status_board(packet: Mapping[str, Any]) -> str`.
- Produces: `StatusBoardValidationFailure(RuntimeError)` for fail-closed validation.
- Produces constants `NETWORK_CALLS=False`, `AUTO_MUTATE=False`, `MAY_MODIFY_PRODUCT_RUNTIME=False`, `MUTATION_AUTHORITY_GRANTED=False`, `GITHUB_ACTIONS_FALLBACK=0`.

- [ ] **Step 1: Write the failing validator tests**

Add tests asserting:

```python
VALID_ACTIVE = {
    "completion_percent": 87,
    "status": "YELLOW",
    "live_active_chat": "API_2",
    "frozen": False,
    "current_blocker": "production SHA convergence",
    "next_legal_action": "consume authoritative deployment result",
}


def test_valid_yellow_active_packet_passes():
    out = validate_status_packet(VALID_ACTIVE)
    assert out["completion_percent"] == 87.0
    assert out["status"] == "YELLOW"
    assert out["live_active_chat"] == "API_2"


def test_valid_red_requires_blocker():
    packet = {**VALID_ACTIVE, "status": "RED", "current_blocker": "blocked"}
    assert validate_status_packet(packet)["status"] == "RED"


def test_red_without_real_blocker_fails():
    packet = {**VALID_ACTIVE, "status": "RED", "current_blocker": "   "}
    with pytest.raises(StatusBoardValidationFailure):
        validate_status_packet(packet)


def test_valid_terminal_packet_passes():
    packet = {
        "completion_percent": 100,
        "status": "GREEN",
        "live_active_chat": "NONE_TERMINAL",
        "frozen": True,
        "current_blocker": None,
        "next_legal_action": None,
    }
    assert validate_status_packet(packet)["frozen"] is True
```

Also add individual failing tests for:
- 100% with YELLOW;
- frozen below 100%;
- frozen with RED/YELLOW;
- `NONE_TERMINAL` before terminal;
- missing each mandatory field;
- unknown status;
- unknown chat;
- percentage below 0 or above 100;
- `completion_percent=True`;
- `NaN` and positive/negative infinity;
- terminal GREEN+100+frozen with `THIS_CHAT`, `MONSTER`, or `API_2` must fail because terminal ownership is `NONE_TERMINAL`.

- [ ] **Step 2: Run validator tests and confirm RED**

Run:

```bash
python -m pytest -q tests/test_devsystem_universal_live_status_board_v1.py
```

Expected: collection/import failure because `devsystem.universal_live_status_board_v1` does not yet exist.

- [ ] **Step 3: Implement the minimal validator**

Create `devsystem/universal_live_status_board_v1.py` with:

```python
class StatusBoardValidationFailure(RuntimeError): ...

def validate_status_packet(packet: Mapping[str, Any]) -> dict[str, Any]: ...
```

Implementation requirements:
- copy/normalize input; never mutate caller data;
- coerce valid finite numeric completion to `float`;
- reject `bool`, `NaN`, infinity, and values outside `[0,100]`;
- enforce exact enums and all terminal invariants from Global Constraints;
- normalize optional absent support fields to `None`, except `frozen` defaults to `False`;
- make no I/O or network calls.

- [ ] **Step 4: Run validator tests and confirm GREEN**

Run:

```bash
python -m pytest -q tests/test_devsystem_universal_live_status_board_v1.py
```

Expected: validator tests PASS.

- [ ] **Step 5: Write failing renderer tests**

Add tests asserting:

```python
def test_renderer_displays_all_three_mandatory_fields():
    text = render_status_board(VALID_ACTIVE)
    assert "Completion: 87%" in text
    assert "Status: YELLOW" in text
    assert "Live Active Chat: API_2" in text


def test_renderer_is_deterministic_across_input_order():
    a = render_status_board(VALID_ACTIVE)
    b = render_status_board(dict(reversed(list(VALID_ACTIVE.items()))))
    assert a == b


def test_terminal_renderer_shows_green_frozen():
    text = render_status_board({
        "completion_percent": 100,
        "status": "GREEN",
        "live_active_chat": "NONE_TERMINAL",
        "frozen": True,
    })
    assert "Status: GREEN + FROZEN" in text
```

- [ ] **Step 6: Run renderer tests and confirm RED**

Run only the renderer tests.

Expected: FAIL because `render_status_board` is not yet implemented.

- [ ] **Step 7: Implement deterministic renderer**

Add:

```python
def render_status_board(packet: Mapping[str, Any]) -> str: ...
```

Requirements:
- always call `validate_status_packet` first;
- render a fixed line order: title, Completion, Status, Live Active Chat, Current Blocker, Next Legal Action;
- render integer-valued percentages without `.0`, otherwise retain a stable compact decimal form;
- render `GREEN + FROZEN` only for terminal frozen packets;
- use `none` for absent blocker/action;
- do not add ownership inference or lease reads.

- [ ] **Step 8: Run full focused test file and compile**

Run:

```bash
python -m pytest -q tests/test_devsystem_universal_live_status_board_v1.py
python -m py_compile devsystem/universal_live_status_board_v1.py
```

Expected: all tests PASS; compile exits 0.

- [ ] **Step 9: Commit Task 1**

Commit only the module + focused tests with message:

```text
feat: add universal live status board schema
```

---

### Task 2: Step-1 Control-Plane Contracts, Runless Proof, Merge, and Freeze

**Files:**
- Create: `devsystem/execution_plans/universal-live-status-board-v1-step1-mandatory-status-schema.json`
- Create: `devsystem/runless_proof_plans/universal-live-status-board-v1-step1-mandatory-status-schema.json`
- Create: `devsystem/task_ledgers/universal-live-status-board-v1-step1-mandatory-status-schema.json`
- Read-only dependency: `docs/superpowers/specs/2026-10-09-universal-live-status-board-v1-design.md`
- Read-only dependency: `docs/superpowers/plans/2026-10-09-universal-live-status-board-v1-step1-mandatory-status-schema.md`

**Interfaces:**
- Consumes Task 1 module/test artifacts and current Step 2A main/lease/registry truth at execution time.
- Produces one exact Runless proof plan for the Step-1 candidate.
- Produces freeze token `UNIVERSAL_LIVE_STATUS_BOARD_V1_STEP1_MANDATORY_STATUS_SCHEMA_FROZEN`.
- Produces one task ledger that records RED/GREEN proof state without granting authority.

- [ ] **Step 1: Reconcile Step 2A immediately before mutation**

Verify current `main`, current frozen-registry revision/hash, active thaws, and scope-aware lease state. Because API 2 may advance `main` independently, do not hard-code the earlier design-time main SHA as implementation authority.

Acquire exactly one non-overlapping implementation/proof lease covering only:
- `devsystem/universal_live_status_board_v1.py`
- `tests/test_devsystem_universal_live_status_board_v1.py`
- the three Step-1 JSON contract files above
- the approved spec and implementation plan as read-only dependencies.

If a matching authoritative lease/action already exists, reuse it instead of creating another.

- [ ] **Step 2: Create execution plan JSON**

The execution plan must record:
- project `UNIVERSAL_LIVE_STATUS_BOARD_V1`;
- step `1/4`;
- mission `Mandatory Status Schema`;
- exact current base-main SHA from Step 2A;
- mutation scope limited to Task-1/Task-2 artifacts;
- product/runtime/model scope false;
- GitHub Actions fallback false/0;
- freeze token fixed by spec.

- [ ] **Step 3: Create Runless proof plan JSON**

Runless commands must be exactly scoped to Step 1:

```json
[
  ["python", "-m", "pytest", "-q", "tests/test_devsystem_universal_live_status_board_v1.py"],
  ["python", "-m", "py_compile", "devsystem/universal_live_status_board_v1.py"]
]
```

Artifacts must include:
- module;
- focused tests;
- execution plan;
- Runless proof plan;
- task ledger;
- approved spec;
- implementation plan.

Dependencies should include only existing control-plane validators required by Runless/Step 2A, not sports product files.

- [ ] **Step 4: Create task ledger JSON**

Ledger must record:
- problem: status updates can omit/contradict completion, color state, or live-active-chat identity;
- root cause: no shared machine-checkable status schema exists;
- patch: pure validator + deterministic renderer;
- TDD RED/GREEN commit/result fields;
- no product/runtime/model mutation;
- `green_plus_frozen_claimed=false` until independent freeze read-back;
- next legal action = exact-head Runless proof.

- [ ] **Step 5: Run focused local verification again after metadata is sealed**

Run:

```bash
python -m pytest -q tests/test_devsystem_universal_live_status_board_v1.py
python -m py_compile devsystem/universal_live_status_board_v1.py
```

Expected: PASS.

- [ ] **Step 6: Lock exact candidate and submit one Runless proof**

Verify candidate diff contains only the seven Step-1 artifacts declared by the proof plan. Submit exactly one authoritative Runless proof for that candidate.

Required terminal proof:
- `failure_class=NONE`;
- immutable receipt exists;
- `runless-final-gate` SUCCESS;
- GitHub Actions fallback `0`.

No unchanged proof rerun after terminal proof exists.

- [ ] **Step 7: Open at most one PR and exact-head merge**

Before merge verify:
- PR head equals exact Runless-certified candidate;
- base/main has not invalidated authority;
- scope remains exact;
- no frozen artifact outside declared scope changed.

If the exact candidate is already merged while reconciling, consume that truth instead of opening/merging a duplicate PR.

- [ ] **Step 8: Perform post-merge proof reuse**

Use deterministic content-addressed proof reuse when merged-main artifact/dependency blobs match the certified candidate. Do not rerun unchanged static tests solely because a merge commit SHA differs.

Publish/verify merged-main Runless receipt and merged-main `runless-final-gate` SUCCESS.

- [ ] **Step 9: Transactionally freeze Step 1**

CAS-update the frozen-artifact registry with exact token:

```text
UNIVERSAL_LIVE_STATUS_BOARD_V1_STEP1_MANDATORY_STATUS_SCHEMA_FROZEN
```

Freeze exactly the Step-1 artifacts declared by the proof plan. Preserve all unrelated frozen entries and active thaws.

- [ ] **Step 10: Independently read back terminal state**

Verify independently:
- exact freeze token exists;
- `status=FROZEN`;
- source-main SHA equals merged main;
- artifact blobs equal merged-main blobs;
- registry revision advanced exactly once;
- registry state hash validates;
- unrelated thaws preserved;
- merged-main Runless gate SUCCESS;
- GitHub Actions fallback remains `0`.

Only after this read-back set/claim:

```text
Step 1/4 — 100% GREEN + FROZEN
```

- [ ] **Step 11: Release Step-1 authority and stop**

Release/expire the Step-1 implementation/closeout authority. Do not begin Step 2 until the user explicitly asks to proceed.

## Self-Review Result

- Spec coverage: complete for Step 1; ownership resolution, heartbeat recovery, and enforcement remain explicitly deferred to Steps 2–4.
- Step scan: each action has one checkable result; no product-code transcript included.
- Type consistency: `validate_status_packet`, `render_status_board`, enums, and freeze token are consistent across tasks.
- Review Focus coverage: bool percentage, non-finite numeric values, whitespace RED blocker, deterministic dictionary-order rendering, and terminal active-chat contradiction all have explicit tests in Task 1.
- Proportion: plan is implementation-focused and does not duplicate the full four-step design.
