# CFB Game Total Native Page-1 Shell — Step 3 Implementation Plan

**Workstream:** `cfb-game-total-native-website-rebuild-v1`  
**Task:** `cfb-game-total-native-page1-shell-step3-v1`  
**Base main:** `a3166e7d980d85b6adb6a064b8ac225befd9b9e3`

## Goal

Add the native Page-1 visual shell beneath the existing KYRE SPORTS AI site chrome while preserving the Step-1 native route boundary, the Step-2 frozen backend, all schedule/event identity behavior, and selected-event Page 2.

## Global constraints

- Step 2A before every mutation.
- One authoritative branch, PR, proof chain, lease, and closeout.
- `cfb_game_total_clean_page_v39.py` remains immutable.
- Only the Page-1 route pointer in `streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py` may advance, under an exact-head thaw.
- `PAGE2_RUNTIME` must remain `cfb_game_total_page2_step8_final_runtime_v1`.
- No model/projection/probability/market/schedule/provider changes.
- No Phoenix-time selector work in Step 3; that is Step 4.
- No GitHub Actions fallback.

## Task 1 — RED contract

Add `tests/test_cfb_game_total_native_page1_shell_step3_v1.py`. It requires a V40 native shell owner, native shell markers/content, preserved zero-influence guards, Page-1 router ownership at V40, unchanged Page-2 ownership, and no date-selector ownership in V40.

Expected RED cause: V40 does not exist and the router still points Page 1 at V39.

## Task 2 — Minimal shell implementation

Add `cfb_game_total_clean_page_v40.py` as an additive wrapper over V39. Render only the Page-1 shell presentation, then delegate unchanged to V39. Advance only `PAGE1_NATIVE_ROUTE` in the final router from V39 to V40.

## Task 3 — Exact-head certification

Run:

```bash
python -m pytest -q \
  tests/test_cfb_game_total_native_page1_shell_step3_v1.py \
  tests/test_cfb_game_total_native_routing_step1_v1.py \
  tests/test_devsystem_cfb_game_total_backend_preservation_step2_v1.py \
  tests/test_cfb_game_total_page2_step8_final_v1.py
python -m py_compile \
  cfb_game_total_clean_page_v40.py \
  streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py
```

Use Runless `runless-final-gate` app id `5204253`. Before proof, authorize one exact-head thaw for the frozen final router from blob `7f27ead880acdbe6a272e6d34dfcd55d84a926d0` to the candidate router blob. Merge only the exact certified candidate.

## Task 4 — Finalization Authority closeout

Reuse premerge static evidence on merged main with `static_evidence_reexecuted=false` and `github_actions_enabled=false`. Atomically forward-port the frozen router baseline, retire only the Step-3 thaw, add `CFB_GAME_TOTAL_NATIVE_WEBSITE_REBUILD_STEP3_PAGE1_SHELL_V1_FROZEN`, preserve unrelated thaws, release the exact Step-3 lease, and read back main/gate/receipt/registry/lease before claiming GREEN + FROZEN.
