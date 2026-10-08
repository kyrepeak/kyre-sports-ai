# CFB Game Total Page 1 V2 — Step 2 Multi-Source Data Engine

**Goal:** Make Page 1 consume verified multi-source display evidence so Third Down and History no longer terminate in generic `DATA LIMITED`, while preserving all frozen model/projection behavior.

**Base:** `8563157c27fe3c13a3084e79230910cdb5e0841a`

## Global constraints

- Step 2 / 9 only.
- Kyre Sports API remains primary page-facing identity/market transport where it already owns those fields.
- Reuse the certified `cfb_game_total_step4_multisource_v1` official-audit + cfbstats fallback; do not create an ESPN-only dependency.
- Enrichment is display-only. Projection, probability, qualification, ranking, distribution, and sportsbook projection influence remain unchanged.
- Never overwrite an already verified Page-1 `official_stats` row.
- History means only verified completed-game sample evidence. If no exact prior meeting appears in available verified samples, say exactly that; never invent all-time series history.
- Keep `app.py` and all WNBA artifacts untouched.
- Activate through the existing CFB-only Router V190 binding.
- GitHub Actions fallback = 0. Runless is the only final proof path.
- Exact-head merge + post-merge proof reuse + frozen-registry read-back are mandatory.

## Task 1 — TDD contract

Create `tests/test_cfb_game_total_page1_v2_step2_multisource_data_engine.py` first. It must fail because the Step-2 engine/Page V35 do not yet exist.

Expected RED: `Step-2 multi-source Page-1 engine must exist` or equivalent missing-module/file failure.

## Task 2 — Multi-source engine

Create `cfb_game_total_page1_multisource_v1.py`.

- Call `cfb_game_total_step4_multisource_v1.build_display_fallback(...)` on copied display inputs.
- Convert verified fallback metrics into V159-compatible `official_stats` rows for missing Third Down, Red Zone, and Turnover fields.
- Preserve existing rows.
- Build truthful `history` context from exact opponent matches in verified `completed_games` samples.
- When no exact meeting is present, populate a truthful non-empty status describing the verified sample rather than generic `DATA LIMITED`.
- Return diagnostics proving source, filled row count, history state, and 0.0 sportsbook projection influence.

## Task 3 — Page and CFB-only route activation

Create `cfb_game_total_clean_page_v35.py` as an additive successor to V34. Temporarily patch V24's display reconciliation handoff during render, enrich the copied display bundle, and restore the original function in `finally`.

Update only Router V190's `GAME_TOTAL_PAGE` binding from V34 to V35. Do not touch `app.py`, WNBA routers, shared models, or frozen Step 1 artifacts.

## Task 4 — Verification and closeout

Run the focused Step-2 test. Then use one exact-head Runless proof chain. On GREEN: merge exact head, reuse static proof on merged-main if content identity is unchanged, freeze the Step-2 artifacts, and read back the canonical registry entry.

**Completion token:** `CFB_GAME_TOTAL_PAGE1_V2_STEP2_MULTISOURCE_DATA_ENGINE_FROZEN`
