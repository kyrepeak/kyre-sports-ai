# Universal Live Status Board V1 — Step 2 Authoritative Chat Ownership Registry

## Mission
Bind `live_active_chat` to the existing scope-aware execution lease truth so the board cannot rely on memory or manual labels.

## Constraints
- Reuse `devsystem/scope_aware_execution_lease_v1.py`; do not create a second ownership registry.
- Preserve Step 2A and cross-workstream isolation.
- One live authoritative owner is required for active packets; zero or multiple live owners fail closed.
- `chatgpt:monster-v2:*` maps to `MONSTER`.
- `chatgpt:api2:*` maps to `API_2`.
- Other valid single owners map to `THIS_CHAT`.
- Terminal GREEN + 100% + frozen packets require zero live owners and bind to `NONE_TERMINAL`.
- No sports product/runtime/model/projection mutation.
- GitHub Actions fallback remains 0.

## TDD acceptance
1. single MONSTER owner maps to MONSTER;
2. single API 2 owner maps to API_2;
3. single non-reserved owner maps to THIS_CHAT;
4. no live owner fails closed for active resolution;
5. multiple live owners fail closed;
6. expired holders are ignored;
7. invalid lease state fails closed;
8. binding overrides a manual chat label with lease truth;
9. terminal binding with no live owner emits NONE_TERMINAL;
10. terminal binding fails while any live owner remains;
11. Step-1 schema and renderer regressions remain green.

## Implementation
Add pure, side-effect-free ownership resolution and packet-binding helpers to `devsystem/universal_live_status_board_v1.py`. Validate the supplied lease state using the existing scope-aware lease validator and derive the live holder set from authoritative holder expiry timestamps. Do not acquire, renew, release, or mutate leases.

## Verification
Run:
- `python -m pytest -q tests/test_devsystem_universal_live_status_board_v1.py`
- `python -m py_compile devsystem/universal_live_status_board_v1.py`

Then obtain one exact-head Runless receipt, exact-head merge, deterministic post-merge proof reuse, transactional frozen-registry update, independent read-back, and release finalization authority.

Freeze token: `UNIVERSAL_LIVE_STATUS_BOARD_V1_STEP2_AUTHORITATIVE_CHAT_OWNERSHIP_FROZEN`.
