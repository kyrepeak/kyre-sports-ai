# MONSTER NBA PRA Page 2 V4 CSS Cache Bust R2

**Goal:** Make the already-correct V4 stylesheet source take effect in the long-running Streamlit process by evicting only the stale NBA PRA Page 2 modules at app bootstrap.

**Scope:** Presentation/runtime convergence only. No model, projection, provider, routing, Page 1 analytics, or sportsbook logic changes.

## Implementation
- Add exact `sys.modules.pop(..., None)` calls for `nba_pra_runtime_v2`, `nba_pra_page2_sync_v1`, and `nba_pra_page2_command_center_v4` in the existing `app.py` cache-bust block.
- Keep `importlib.invalidate_caches()` after those evictions and before the lazy router import.
- Preserve the sealed V4 `_css()` composition from R1.

## Acceptance
- RED test proves current main lacks the three evictions while sealed V4 source is already correct.
- GREEN tests prove all three evictions occur before lazy routing and V4 still returns one valid style envelope.
- Existing V4 and R1 regression suites remain GREEN.
- Live mobile browser must reach Page 2 READY on the exact merged runtime and find every V4 section while raw `.p2v4-*` CSS is absent from visible text.
