# CFB Game Total Page 1 V2 — Step 1 Audit Contract

## Authority

This contract defines the additive Page-1 V2 workstream above the frozen CFB Game Total implementation. Step 1 is audit/control-plane only: **no product runtime mutation** is permitted here. The rollback/main identity is `371f05b940369c3378ceea8f12fb02e52e5f7f11`.

The audited live Page-1 ownership chain is:
- `streamlit_memory_lazy_router_v190.py` binds the active Game Total route to `cfb_game_total_clean_page_v34.py`.
- `cfb_game_total_clean_page_v34.py` is presentation-only and preserves the frozen V33/V28 behavior beneath it.
- `cfb_game_total_clean_page_v11.py` owns the current day selector and Phoenix-date default.
- `cfb_game_total_clean_page_v14.py` owns the visible selected-day game strip and exact-event handoff.

## Root cause

The current date owner already uses `America/Phoenix`, but its default is the current Phoenix calendar date and its visible seven-day range begins two days before the selected date. The selector then loads that selected day's slate and falls back to index 0 when no exact event is supplied. That behavior is incompatible with the new Page-1 requirement because today may contain games that are already in progress or final.

## Future-only Phoenix rule

`America/Phoenix` is the canonical timezone for Page 1. **Today is excluded.** The earliest eligible default slate is **tomorrow and beyond** according to Phoenix local time. An in-progress or final game must never become the default showcase matchup. Date/game navigation in later implementation steps must preserve the same future-only rule.

## Page-facing API and source policy

The **Kyre Sports API** is the primary Page-1 transport/aggregation surface. Current ownership is partial rather than complete: the existing page already uses Kyre Sports API for verified selector identity and sportsbook context, while other display evidence still comes through certified NCAA, ESPN/environment, and cfbstats recovery paths.

Page 1 therefore adopts an explicit **multi-source** policy. ESPN-only ownership is forbidden. Research/enrichment may use official NCAA data, conference/team sources, Kyre Sports API data, verified market feeds, weather/environment sources, cfbstats or other reputable providers when they improve completeness and identity can be reconciled. Provider disagreement must resolve toward authoritative/official evidence or fail closed; no fabricated values are allowed.

The target for later steps is to move complete page-facing fields behind Kyre Sports API aggregation where practical while preserving source provenance and exact event/team identity.

## Zero-generic-empty-state rule

A generic **DATA LIMITED** state is not an acceptable Page-1 terminal UI. Generic data limited placeholders must not be used to hide ordinary provider gaps. Later implementation steps must exhaust the approved source hierarchy and return truthful field-specific states such as Not Posted, Weather Pending, or Game Not Started only when the underlying fact genuinely does not yet exist.

## Frozen analytical boundary

Step 1 does not change projection math, probability, qualification, ranking, sportsbook projection influence, model selection, or frozen Steps 1–12. Existing analytical/model behavior remains frozen. This contract authorizes only the new Page-1 V2 product work in later steps under a fresh Step 2A gate.

## Step-1 acceptance

Step 1 is complete only when this contract is present, the exact owner/root-cause assertions pass, the TDD RED for the missing contract has been observed, Runless exact-head proof passes on the final candidate, the PR merges at the proved head, post-merge identity is verified, and the freeze/read-back receipt records `CFB_GAME_TOTAL_PAGE1_V2_STEP1_AUDIT_LOCK_FROZEN` with GitHub Actions fallback remaining 0.
