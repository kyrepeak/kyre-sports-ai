# Universal Live Status Board V1 — Step 3 Heartbeat + Stale-Owner Recovery

## Mission
Bind the status board to the existing MONSTER V5 heartbeat/dead-man recovery engine so a ghost owner cannot block future work after its heartbeat, authoritative run, and scope lease are all terminal/stale.

## Safety contract
- Reuse `devsystem/execution_heartbeat_deadman_recovery_v1.py`.
- Reuse Step-2 authoritative scope-lease ownership; do not create another owner registry.
- A live heartbeat remains authoritative.
- A stale heartbeat cannot override a still-active authoritative run.
- A terminal run plus stale heartbeat still cannot recover while the old scope lease is live.
- Recovery is eligible only when heartbeat expired + authoritative run terminal + old scope lease expired.
- Unknown run state and continuation drift fail closed.
- Recovery receipts never grant mutation authority; Step 2A and a newly acquired scope lease remain mandatory.
- Recovered board ownership binds only when the heartbeat identity exactly matches the new authoritative lease identity.
- No product/runtime/model/projection mutation.
- GitHub Actions fallback remains 0.

## TDD acceptance
1. live heartbeat + live lease remains authoritative;
2. stale heartbeat + active run waits for terminal event;
3. stale heartbeat + terminal run + live lease blocks recovery;
4. stale heartbeat + terminal run + expired lease becomes recovery eligible;
5. unknown run state fails closed;
6. continuation drift fails closed;
7. heartbeat/lease owner drift fails closed;
8. recovery receipt preserves Step 2A and grants no mutation authority;
9. recovered owner binds only when lease + heartbeat match;
10. recovered binding fails on lease identity drift;
11. Step-1/Step-2/heartbeat-engine regression suites remain green.

## Runless closeout
One exact-head Runless proof request, exact-head merge, deterministic merged-main proof reuse when tree identity permits, transactional freeze-token write, independent read-back, and lease release.

Freeze token: `UNIVERSAL_LIVE_STATUS_BOARD_V1_STEP3_HEARTBEAT_STALE_OWNER_RECOVERY_FROZEN`.
