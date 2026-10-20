# CFB Player Props Page 3 Professional V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing CFB Player Props Page 3 into a premium analytics screen with field-specific source routing, Last-3/Last-5 form, direct player-vs-opponent history, separate team matchup context, and a stronger mobile-first decision hierarchy while preserving the frozen Page-3 model and identity contracts.

**Architecture:** Keep `cfb_player_props_page3_analysis_v1.py`, `cfb_player_props_page3_context_v1.py`, and `cfb_player_props_page3_history_v1.py` read-only. Add one local CFB field-source policy helper and one presentation-only professional composer, then upgrade `cfb_player_props_page3_v1.py` to consume those helpers without changing routing or projection math.

**Tech Stack:** Python 3, Streamlit, pandas, existing CFB Player Props V1/V3 modules, existing universal sports provider registry/field-router policy, pytest, Runless final gate.

**Spec:** `docs/superpowers/specs/2026-10-20-cfb-player-props-page3-professional-v1-design.md`

## Global Constraints

- Parent freeze `MONSTER_CFB_PLAYER_PROPS_PAGE3_V1_FROZEN` remains authoritative and unchanged.
- Do not modify `cfb_player_props_page3_analysis_v1.py`, `cfb_player_props_page3_context_v1.py`, or `cfb_player_props_page3_history_v1.py`.
- Sportsbook projection influence remains exactly `0.0`.
- Required game/player/team/opponent/market identity fails closed.
- Missing/null values remain missing/null; never coerce them to `0`.
- Keep sportsbook-specific observations separate; consensus is derived and labeled.
- Use only 2–4 relevant sources per field family and report only sources actually consulted.
- Prefer direct/official sources before aggregators where semantic coverage is equivalent.
- Cross-check important data with at least two independent sources when available.
- Prefer the newest trustworthy timestamp after identity and semantic validation when equivalent sources disagree.
- A failed provider may fall back only to a source for the same semantic metric.
- No universal-runtime route mutation.
- Back navigation, market switching, identity-keyed slider cleanup, and TOP control remain intact.
- One successor branch/PR/Runless proof path only; no duplicate proof, deployment, lease, or finalization lane.

## Review Focus

1. A configured provider returning `None`, stale data, or malformed timestamps must not become a fabricated zero or outrank a newer valid equivalent source; pinned in Task 1.
2. A player with fewer than five valid history rows must produce honest Last-3/Last-5 sample sizes and never divide by an assumed sample count; pinned in Task 2.
3. Prior team meetings involving a different quarterback/player must never be labeled direct player H2H; pinned in Task 2.
4. A market with no current sportsbook rows must keep the professional page usable and explicitly show unavailable market evidence rather than blank cards; pinned in Task 3.
5. A market/player switch must not retain stale professional or slider state from the previous identity; pinned in Task 3 plus existing Page-3 context regressions.

---

### Task 1: CFB Page-3 Field Source Policy

**Files:**
- Create: `cfb_player_props_page3_source_policy_v1.py`
- Test: `tests/test_cfb_player_props_page3_source_policy_v1.py`

**Interfaces:**
- Consumes: existing provider identifiers/capabilities from `devsystem/contracts/universal-sports-provider-registry-v1.json` and existing source labels emitted by Page-2/Page-3 owners.
- Produces: `FIELD_SOURCE_PRIORITIES: dict[str, tuple[str, ...]]`; `rank_sources(field_family: str, available_provider_ids: Sequence[str]) -> tuple[str, ...]`; `choose_newest_equivalent(rows: Sequence[Mapping[str, Any]], *, timestamp_key: str = "observed_at_utc") -> Mapping[str, Any] | None`; `provenance(field_family: str, consulted_provider_ids: Sequence[str], *, newest_timestamp: str = "") -> dict[str, Any]`.

- [ ] **Step 1: Write the failing source-policy tests**

Add tests named:
- `test_field_priorities_use_two_to_four_relevant_sources_only`
- `test_direct_or_official_sources_rank_before_aggregators`
- `test_unavailable_sources_are_filtered_without_becoming_active`
- `test_newest_equivalent_row_wins_without_null_to_zero_coercion`
- `test_provenance_reports_only_consulted_sources`
- `test_sportsbook_field_keeps_book_specific_source_family`

Assert the exact field families: `player_props`, `game_lines`, `player_stats`, `game_state`, `history`, `availability`, and the spec-defined preference order for each family.

- [ ] **Step 2: Run the new tests and verify RED**

Run: `python -m pytest --noconftest -q tests/test_cfb_player_props_page3_source_policy_v1.py`

Expected: FAIL because `cfb_player_props_page3_source_policy_v1` does not exist.

- [ ] **Step 3: Implement the source-policy interfaces**

Create `cfb_player_props_page3_source_policy_v1.py` with the exact interfaces above. Provider names may be present in policy while unconfigured, but `rank_sources` must return only IDs present in `available_provider_ids`, capped at four, preserving policy order. `choose_newest_equivalent` ignores rows with invalid/missing timestamps when a timestamped equivalent exists and never rewrites field values. `provenance` returns only actually consulted providers.

- [ ] **Step 4: Run Task-1 tests and verify GREEN**

Run: `python -m pytest --noconftest -q tests/test_cfb_player_props_page3_source_policy_v1.py`

Expected: all Task-1 tests PASS.

- [ ] **Step 5: Commit Task 1**

Commit message: `feat: add CFB Page 3 field source policy`

---

### Task 2: Professional History and Decision Composer

**Files:**
- Create: `cfb_player_props_page3_professional_v1.py`
- Test: `tests/test_cfb_player_props_page3_professional_v1.py`

**Interfaces:**
- Consumes: frozen Page-3 analysis packet from `cfb_player_props_page3_analysis_v1.build_page3_analysis(...)`, `selected_line`, current exact context, and Task-1 source policy helpers.
- Produces: `build_recent_window(rows: Sequence[Mapping[str, Any]], *, limit: int, selected_line: float | None) -> dict[str, Any]`; `build_direct_opponent(rows: Sequence[Mapping[str, Any]], *, opponent_team_id: str, selected_line: float | None) -> dict[str, Any]`; `build_team_matchup(rows: Sequence[Mapping[str, Any]], *, opponent_team_id: str, selected_player_id: str) -> dict[str, Any]`; `build_professional_view(context: Mapping[str, Any], packet: Mapping[str, Any], *, selected_line: float | None) -> dict[str, Any]`.

- [ ] **Step 1: Write failing professional-composer tests**

Add tests named:
- `test_recent_windows_return_honest_last3_and_last5_samples`
- `test_recent_window_hit_rate_uses_only_numeric_production`
- `test_direct_opponent_requires_exact_opponent_team_id`
- `test_team_matchup_does_not_masquerade_as_player_h2h`
- `test_quarterback_detail_omits_unverified_optional_stats_instead_of_zero`
- `test_opponent_vs_role_unavailable_has_no_directional_claim`
- `test_decision_view_uses_frozen_projection_and_selected_line_only`
- `test_professional_view_does_not_mutate_input_packet`
- `test_sportsbook_projection_influence_remains_zero`

Use fixtures with 2, 3, 5, and 6 history rows so short-sample behavior is explicit.

- [ ] **Step 2: Run Task-2 tests and verify RED**

Run: `python -m pytest --noconftest -q tests/test_cfb_player_props_page3_professional_v1.py`

Expected: FAIL because the composer module does not exist.

- [ ] **Step 3: Implement recent-form and H2H helpers**

Implement `build_recent_window`, `build_direct_opponent`, and `build_team_matchup`. Last-3/Last-5 summaries expose `sample_size`, `average`, `hits`, `hit_rate`, `rows`, `sources`, and `newest_timestamp`; hit rates use only numeric production rows and an actual selected line. Direct H2H filters by exact opponent team ID. Team-matchup output is a separate semantic block and must never reuse the direct-H2H label.

- [ ] **Step 4: Implement `build_professional_view`**

Return presentation blocks for `decision`, `last3`, `last5`, `direct_opponent`, `team_matchup`, `opponent_vs_role`, `sportsbook_board`, `market_movement`, `reasoning`, and `quality`. It may enrich presentation context but must not modify the frozen packet or projection. Optional QB detail keys are included only when numeric verified values exist.

- [ ] **Step 5: Run Task-2 tests and verify GREEN**

Run: `python -m pytest --noconftest -q tests/test_cfb_player_props_page3_professional_v1.py`

Expected: all Task-2 tests PASS.

- [ ] **Step 6: Commit Task 2**

Commit message: `feat: compose professional CFB Page 3 intelligence`

---

### Task 3: Premium Page-3 Presentation

**Files:**
- Modify: `cfb_player_props_page3_v1.py`
- Test: `tests/test_cfb_player_props_page3_professional_v1.py`
- Existing regression tests: `tests/test_cfb_player_props_page3_v1.py`, `tests/test_cfb_player_props_page3_context_v1.py`, `tests/test_cfb_player_props_page3_line_lab_v1.py`, `tests/test_cfb_player_props_page3_integration_v1.py`

**Interfaces:**
- Consumes: `cfb_player_props_page3_professional_v1.build_professional_view(...)` plus the existing frozen `page3_analysis` packet and existing `line_lab` slider.
- Produces: the same `render_cfb_player_props_page3() -> None` route entrypoint with upgraded visual hierarchy only.

- [ ] **Step 1: Add failing UI-contract assertions**

Extend `tests/test_cfb_player_props_page3_professional_v1.py` with source-contract tests requiring:
- `MODEL DECISION` section;
- `LINE LAB` retained;
- `LAST 3` and `LAST 5` recent-form labels;
- `DIRECT PLAYER VS OPPONENT` and separate `TEAM MATCHUP HISTORY` labels;
- `OPPONENT VS ROLE` section;
- `SPORTSBOOK MARKET` board;
- `WHY THE MODEL SEES IT THIS WAY` evidence cards;
- `DATA QUALITY & SOURCES` section;
- `← Back to Game Props` and fixed `↑ TOP` control;
- no `st.number_input` or `st.text_input` path;
- import/use of `cfb_player_props_page3_professional_v1`.

- [ ] **Step 2: Run the new UI-contract assertions and verify RED**

Run: `python -m pytest --noconftest -q tests/test_cfb_player_props_page3_professional_v1.py`

Expected: FAIL on the missing professional UI contract.

- [ ] **Step 3: Upgrade the hero and decision hierarchy**

Modify `cfb_player_props_page3_v1.py` to retain black/glacier-blue styling while adding larger mobile-safe typography, premium player/team hero treatment, current prop/line/freshness badges, and a compact decision bar showing projection, selected/current line, margin, Over/Under probability, confidence/evidence state, and deterministic lean.

- [ ] **Step 4: Upgrade Line Lab and evidence sections**

Keep the existing slider and identity-keyed state. Add projection/current-market markers using captions/metrics supported by Streamlit without introducing keyboard input. Render Last-3/Last-5 recent form, direct player H2H, separate team matchup history, opponent-vs-role context, sportsbook-specific market rows, movement, reasoning/risk cards, and source-quality metadata from the professional view.

- [ ] **Step 5: Make unavailable states explicit and compact**

For every optional section, render a clear unavailable caption rather than a blank card or zero. Keep the page usable when sportsbook rows or supplemental history are absent.

- [ ] **Step 6: Run focused professional + existing Page-3 regressions**

Run:
`python -m pytest --noconftest -q tests/test_cfb_player_props_page3_professional_v1.py tests/test_cfb_player_props_page3_v1.py tests/test_cfb_player_props_page3_context_v1.py tests/test_cfb_player_props_page3_line_lab_v1.py tests/test_cfb_player_props_page3_integration_v1.py`

Expected: all selected tests PASS.

- [ ] **Step 7: Commit Task 3**

Commit message: `feat: redesign CFB Page 3 professional analytics UI`

---

### Task 4: Successor Control Metadata and Exact-Head Proof Contract

**Files:**
- Create: `devsystem/task_ledgers/monster-cfb-player-props-page3-professional-v1.json`
- Create: `devsystem/runless_proof_plans/monster-cfb-player-props-page3-professional-v1.json`
- Test: existing full CFB Page-3/current-runtime regression bundle

**Interfaces:**
- Consumes: exact successor branch head after Tasks 1–3, parent freeze `MONSTER_CFB_PLAYER_PROPS_PAGE3_V1_FROZEN`, scope lease `SCOPE-LEASE-5B3FE9DA17B4BF0A67A81C90`.
- Produces: task ID/workstream `monster-cfb-player-props-page3-professional-v1`, successor freeze token `MONSTER_CFB_PLAYER_PROPS_PAGE3_PROFESSIONAL_V1_FROZEN`, and one Runless proof plan bound to the authoritative exact PR head.

- [ ] **Step 1: Create successor task ledger**

Record source main `88cc62f815456890a8ba007be7cd6d927c6a15a2`, parent freeze token, successor freeze token, scope lease ID, branch/workstream identity, frozen-owner preservation, sportsbook projection influence `0.0`, and the four-task implementation summary.

- [ ] **Step 2: Create the Runless proof plan**

Artifacts must include the two new product helpers, `cfb_player_props_page3_v1.py`, both new test files, task ledger, Runless plan, and the approved spec/implementation plan. Commands must compile the new modules and current Page-3 entrypoint, run the new tests plus the complete existing Page-3/CFB regression bundle, retain the known single stale NFL V4 direct-app assertion deselection only if it is still present and still unrelated, and run `python -m devsystem.api2_universal_runtime_v5_cert`.

- [ ] **Step 3: Run fresh exact-branch verification before requesting Runless**

Run the commands encoded in the proof plan against the exact current successor head. Expected: compile GREEN, focused/full CFB regressions GREEN, Runtime V5 certification GREEN.

- [ ] **Step 4: Open/reuse exactly one successor PR and request exactly one authoritative Runless proof**

Bind proof to the exact PR head and exact expected current main. Do not create a second PR/proof/lease if one exists.

- [ ] **Step 5: If proof fails, classify once before patching**

Inspect the terminal proof result. Patch only the proven root cause on the same authority path when legally mutable. Never repeatedly poll or issue duplicate proof requests for the same unchanged candidate.

- [ ] **Step 6: Merge only after exact-head `runless-final-gate` SUCCESS**

Use App ID `5204253`, required check `runless-final-gate`, and expected-head protection. If main advanced, classify overlap; carry forward only non-overlapping main drift into the same authority path before a new exact-head proof.

- [ ] **Step 7: Complete successor finalization**

Verify merged-main provenance; write/read back the successor finalization-ledger record with token `MONSTER_CFB_PLAYER_PROPS_PAGE3_PROFESSIONAL_V1_FROZEN`; preserve unrelated thaws/records; close out Runless to `GREEN_FROZEN`; release the exact scope lease; re-read main, Runless state, ledger manifest/record, and lease state before declaring 100%.

- [ ] **Step 8: Final GREEN + FROZEN evidence**

Report exact merged-main SHA, exact proved candidate, PR number, Runless proof ID/state, freeze token, ledger revision/state hash, scope lease released state, and zero duplicate authority paths.
