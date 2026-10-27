# MONSTER NBA PRA Page 2 V4 Module Cache R2

Authority: MONSTER ONLY.

## Proven live failure
Production `app.py` heartbeat is current, but Page 2 still renders the pre-repair V4 stylesheet as visible text. Therefore root entrypoint source refresh occurred without a full Python process restart.

## Root cause
`nba_pra_page2_sync_v1` and `nba_pra_page2_command_center_v4` can remain in `sys.modules` across Streamlit source-only reruns. The cached sync module retains the old imported `_css` function even though repository source is repaired.

## Repair
Immediately before the existing `importlib.invalidate_caches()` in root `app.py`, evict exactly:
- `nba_pra_page2_sync_v1`
- `nba_pra_page2_command_center_v4`

No model, data, provider, sportsbook, projection, routing, or renderer source changes.

## Acceptance
1. RED test fails on baseline because both evictions are absent.
2. Focused Page 2 suite passes after the two-line patch.
3. Runless App 5204253 authorizes exact candidate head using a MONSTER-only proof receipt.
4. Expected-head merge succeeds and merged tree matches the tested candidate tree.
5. Fresh 390x844 production browser reaches Page 2 READY with all V4 sections.
6. Production visible text contains no `/* MONSTER NBA PRA Page 2 V4`, `.p2v4-`, or `hero:before{content`.
7. MONSTER-only frozen checkpoint is written and independently read back before 100% GREEN + FROZEN.
