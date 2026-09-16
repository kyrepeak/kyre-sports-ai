# CFB Game Total V152 Production Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the real deployed Streamlit Game Total page run the active V152 router and reliably show exact team identity/logos, current records/stats, accessible evidence, and the compact Monster dashboard without changing frozen Step 11/12 calculations.

**Architecture:** V152 is additive over Router V151. `app.py` becomes the real production handoff to V152; V152 delegates all non-Game-Total routes to V151. Display-only reconciliation continues on a copied game object, while frozen Step 11/12 analysis remains on the original game. Production verification is upgraded to fail closed when the deployed Streamlit heartbeat is stale.

**Tech Stack:** Python 3.12, Streamlit, Playwright, pytest, GitHub Actions, existing CFB runtime reconciliation + strict ESPN logo resolver.

**Spec:** `docs/superpowers/specs/2026-09-16-cfb-game-total-v152-production-rebuild-design.md`

## Global Constraints

- Game Total Step 11 distribution math stays frozen.
- Game Total Step 12 synthesis/grade/tier/threshold/Top-5 logic stays frozen.
- Sportsbook projection influence remains exactly `0.0%`.
- CFB Moneyline and Over/Under stay frozen.
- Display reconciliation must never mutate the game object used by frozen calculations.
- Each completed checkpoint stays closed unless a new failure directly invalidates its acceptance criteria.
- Progress is reported as `X/8 complete — Y left` using 🟢/🟡/🔴.

---

### Task 1: Activate V152 from the real production entrypoint

**Files:**
- Create: `streamlit_memory_lazy_router_v152.py`
- Modify: `app.py`
- Create: `tests/test_cfb_game_total_v152_activation.py`
- Modify: `tests/conftest.py`

**Interfaces:**
- Consumes: `streamlit_memory_lazy_router_v151.render_app`, `record_bootstrap_import_ms`.
- Produces: `streamlit_memory_lazy_router_v152.render_app()`, `PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V152_PRODUCTION_ACTIVE"`.

- [ ] **Step 1: Write the failing activation test**

```python
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_real_app_boots_v152():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_v152" in source
    assert "CFB_GAME_TOTAL_V152_PRODUCTION_ACTIVE" in (ROOT / "streamlit_memory_lazy_router_v152.py").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run it and verify RED**

Run: `python -m pytest -q tests/test_cfb_game_total_v152_activation.py`
Expected: FAIL because V152 does not exist and `app.py` still boots the older router chain.

- [ ] **Step 3: Add the minimal additive router**

```python
import streamlit_memory_lazy_router_v151 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V152 • CFB GAME TOTAL PRODUCTION REBUILD"
PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V152_PRODUCTION_ACTIVE"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v151"


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def render_app() -> None:
    return prior.render_app()
```

Then change the active production import in `app.py` so the `record_bootstrap_import_ms` / `render_app` pair comes from `streamlit_memory_lazy_router_v152` rather than the stale active router.

- [ ] **Step 4: Advance `tests/conftest.py` to V152 without deleting frozen V150/V151 assertions**

The permanent CFB lane must compile V152 and assert the production app references V152.

- [ ] **Step 5: Run activation + permanent CFB collection tests**

Run: `python -m pytest -q tests/test_cfb_game_total_v152_activation.py tests/test_cfb_game_total_dashboard_v151.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app.py streamlit_memory_lazy_router_v152.py tests/test_cfb_game_total_v152_activation.py tests/conftest.py
git commit -m "fix: activate CFB Game Total V152 in production entrypoint"
```

---

### Task 2: Make stale Streamlit deployment fail production verification

**Files:**
- Create: `devsystem/production_verify_v3.py`
- Create: `tests/test_devsystem_production_verify_v3.py`
- Modify: `.github/workflows/devsystem-production-verification.yml`

**Interfaces:**
- Consumes: `devsystem.production_verify_v2.run()` and the existing production Streamlit target.
- Produces: a V3 verifier requiring `CFB_GAME_TOTAL_V152_PRODUCTION_ACTIVE` and writing observed/expected router identity into production evidence.

- [ ] **Step 1: Write tests for fresh and stale heartbeats**

```python
def test_v152_heartbeat_required():
    import devsystem.production_verify_v3 as verify
    assert verify.GAME_TOTAL_REQUIRED_HEARTBEAT == "CFB_GAME_TOTAL_V152_PRODUCTION_ACTIVE"

def test_stale_body_is_rejected():
    import pytest
    from devsystem.production_verify_v3 import _assert_v152_heartbeat, ProductionVerificationFailure
    with pytest.raises(ProductionVerificationFailure):
        _assert_v152_heartbeat("CFB GAME TOTAL • MONSTER DASHBOARD")
```

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest -q tests/test_devsystem_production_verify_v3.py`
Expected: FAIL because V3 does not exist.

- [ ] **Step 3: Implement V3 as an additive wrapper**

`_assert_v152_heartbeat(body: str)` must raise unless the exact V152 heartbeat is present. `run()` first preserves V2 API/Render verification, then drives the deployed Streamlit Game Total route and records `expected_router`, `observed_heartbeat`, and workflow `GITHUB_SHA` when available.

- [ ] **Step 4: Advance the production workflow**

Change the self-test command to include `tests/test_devsystem_production_verify_v3.py` and run `python devsystem/production_verify_v3.py --artifact-dir artifacts/production-verification`.

- [ ] **Step 5: Run production-verifier unit tests**

Run: `python -m pytest -q tests/test_devsystem_production_verify_v1.py tests/test_devsystem_production_verify_v2.py tests/test_devsystem_production_verify_v3.py tests/test_devsystem_production_identity_verify_v1.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add devsystem/production_verify_v3.py tests/test_devsystem_production_verify_v3.py .github/workflows/devsystem-production-verification.yml
git commit -m "test: fail production verification on stale Game Total deployment"
```

---

### Task 3: Build exact team identity before claiming verification

**Files:**
- Create: `cfb_game_total_clean_page_v3.py`
- Create: `tests/test_cfb_game_total_v152_identity.py`
- Modify: `streamlit_memory_lazy_router_v152.py`

**Interfaces:**
- Consumes: `cfb_game_total_clean_page_v2._display_bundle`, `cfb_over_under_logo_resolver_v3.resolve_visuals`.
- Produces: `_identity_state(display_game, away, home, visuals) -> dict` with `verified`, exact IDs, logos, conference/rank, kickoff/venue/broadcast/status.

- [ ] **Step 1: Write identity tests**

Tests must prove `verified` is false when either exact team ID is missing and true only when both exact IDs and both logo URLs are present. Venue/broadcast may remain `unavailable` without falsely invalidating canonical team identity.

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest -q tests/test_cfb_game_total_v152_identity.py`
Expected: FAIL because V3 page/identity state does not exist.

- [ ] **Step 3: Implement `_identity_state` and V152 hero rendering**

Use exact reconciled ESPN IDs only. Never fuzzy-match or synthesize IDs. Render `IDENTITY VERIFIED` only when `verified is True`; otherwise render amber `IDENTITY CHECK`.

- [ ] **Step 4: Point Router V152 Game Total only to Clean Page V3**

Set `ACTIVE_PAGE = "cfb_game_total_clean_page_v3"` while non-Game-Total paths continue to `prior.render_app()`.

- [ ] **Step 5: Run identity + frozen-boundary tests**

Run: `python -m pytest -q tests/test_cfb_game_total_v152_identity.py tests/test_cfb_game_total_dashboard_v151.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add cfb_game_total_clean_page_v3.py streamlit_memory_lazy_router_v152.py tests/test_cfb_game_total_v152_identity.py
git commit -m "feat: require exact identity for V152 Game Total heroes"
```

---

### Task 4: Populate real records and completed-game stats

**Files:**
- Modify: `cfb_game_total_clean_page_v3.py`
- Modify: `cfb_over_under_runtime_team_data_v1.py`
- Create: `tests/test_cfb_game_total_v152_team_stats.py`

**Interfaces:**
- Consumes: reconciled `completed_games` rows.
- Produces: display metrics for record, PPG, allowed/game, point differential/game, recent scoring/allowed, last-5, home/away split, and SOS coverage.

- [ ] **Step 1: Write tests with deterministic completed-game fixtures**

Use fixtures containing wins/losses and points for/against. Assert derived record and averages. Add a snapshot-profile test proving `completed_games` is copied through `_profile_from_snapshot` when present.

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest -q tests/test_cfb_game_total_v152_team_stats.py`
Expected: at least the snapshot completed-games assertion fails.

- [ ] **Step 3: Carry completed-game rows through the runtime snapshot adapter and derive display metrics**

Do not invent metrics for an empty sample. Return `None`/`—` plus `CHECK` quality when unsupported.

- [ ] **Step 4: Re-run team-stat tests**

Run: `python -m pytest -q tests/test_cfb_game_total_v152_team_stats.py`
Expected: PASS.

- [ ] **Step 5: Re-run the live Syracuse @ Pittsburgh regression proof**

Run: `python -m devsystem.cfb_game_total_live_evidence_qa_v1`
Expected: records are usable, exact-ID logos resolve, PPG/allowed/game exist, and completed-game evidence is non-empty.

- [ ] **Step 6: Commit**

```bash
git add cfb_game_total_clean_page_v3.py cfb_over_under_runtime_team_data_v1.py tests/test_cfb_game_total_v152_team_stats.py
git commit -m "fix: carry completed games into V152 team evidence"
```

---

### Task 5: Add the two-team Evidence Center

**Files:**
- Modify: `cfb_game_total_clean_page_v3.py`
- Create: `tests/test_cfb_game_total_v152_evidence_center.py`

**Interfaces:**
- Produces: `_render_evidence_center(...)` with always-visible summary metrics and two independent expanders named `Syracuse evidence` / `Pittsburgh evidence` dynamically by team.

- [ ] **Step 1: Write source/UI contract tests**

Assert visible labels `PPG`, `ALLOWED / GAME`, `POINT DIFF / GAME`, `RECENT FORM`, `DATA SOURCE`, and independent team evidence expander labels exist before deep audit/model sections.

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest -q tests/test_cfb_game_total_v152_evidence_center.py`
Expected: FAIL until V152 evidence center exists.

- [ ] **Step 3: Implement the Evidence Center**

Each team expander contains recent completed games, offense/defense evidence, split/SOS context, NCAA/ranking provenance, and reconciliation source notes. Always-visible summary remains above the expanders.

- [ ] **Step 4: Run evidence-center tests**

Run: `python -m pytest -q tests/test_cfb_game_total_v152_evidence_center.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cfb_game_total_clean_page_v3.py tests/test_cfb_game_total_v152_evidence_center.py
git commit -m "feat: add compact V152 team evidence center"
```

---

### Task 6: Finish the compact fun Monster layout

**Files:**
- Modify: `cfb_game_total_clean_page_v3.py`
- Create: `tests/test_cfb_game_total_v152_layout.py`

**Interfaces:**
- Produces visible markers `V152 PRODUCTION ACTIVE`, two team hero cards, compact game strip, scoring-vs-defense summary, collapsed deep audit, collapsed Top-5 scan.

- [ ] **Step 1: Write layout contract tests**

Assert critical content order: header < heroes < game strip < evidence summary < evidence center < model gate < deep audit. Assert deep audit and Top-5 use `st.expander(..., expanded=False)` and CSS includes mobile one-column reflow without fixed outer width.

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest -q tests/test_cfb_game_total_v152_layout.py`
Expected: FAIL before final V152 layout markers exist.

- [ ] **Step 3: Implement the responsive visual hierarchy**

Use green for healthy/verified, red for failures, amber for incomplete/check, blue for neutral facts, purple for Monster/model, gray for support text. Do not wrap every card in green borders.

- [ ] **Step 4: Run layout + evidence tests**

Run: `python -m pytest -q tests/test_cfb_game_total_v152_layout.py tests/test_cfb_game_total_v152_evidence_center.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cfb_game_total_clean_page_v3.py tests/test_cfb_game_total_v152_layout.py
git commit -m "feat: finish compact V152 Game Total dashboard"
```

---

### Task 7: Certify the real app with branch-local and deployed Playwright

**Files:**
- Create: `devsystem/cfb_game_total_browser_qa_v2.py`
- Create: `.github/workflows/cfb-game-total-v152-browser.yml`
- Create: `tests/test_cfb_game_total_browser_v152.py`

**Interfaces:**
- Consumes the real `app.py` entrypoint locally and the configured production Streamlit URL after merge.
- Produces screenshots + JSON proof with route, heartbeat, identity, logo, record/evidence, expander, and frozen-sportsbook assertions.

- [ ] **Step 1: Write browser-contract source tests**

Require these markers/assertions in V2 QA: exact heartbeat, two logo elements, non-placeholder records when completed-game evidence is present, evidence expanders open successfully, deep audit collapsed by default, `0.0%` visible.

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest -q tests/test_cfb_game_total_browser_v152.py`
Expected: FAIL because V2 browser QA does not exist.

- [ ] **Step 3: Implement V2 browser QA by extending the proven V1 navigation pattern**

Use the existing frame discovery and selector navigation. Save `cfb_game_total_v152.png` and `cfb_game_total_v152.json` evidence.

- [ ] **Step 4: Add V152 workflow**

Start branch-local Streamlit with `python -m streamlit run app.py`, run V2 QA against `http://127.0.0.1:8501`, upload evidence, and always terminate Streamlit.

- [ ] **Step 5: Run branch-local browser proof**

Run Streamlit locally in CI/workspace and then:
`python -m devsystem.cfb_game_total_browser_qa_v2 --base-url http://127.0.0.1:8501 --artifact-dir artifacts/cfb-game-total-v152`
Expected: GREEN.

- [ ] **Step 6: Commit**

```bash
git add devsystem/cfb_game_total_browser_qa_v2.py .github/workflows/cfb-game-total-v152-browser.yml tests/test_cfb_game_total_browser_v152.py
git commit -m "test: certify V152 Game Total through real app browser"
```

---

### Task 8: Run full gates, merge, prove production, and freeze

**Files:**
- Create: `devsystem/task_ledgers/cfb-game-total-v152-production-rebuild.json`
- Update only the existing final freeze/evidence manifest required by the repo after successful production proof.

**Interfaces:**
- Produces the final certified `main` SHA, rollback parent, green production evidence, and closed Anti-Loop task state.

- [ ] **Step 1: Create exactly one task ledger for this non-doc implementation**

Use the existing V2 ledger schema with `task_id = "cfb-game-total-v152-production-rebuild"` and active status until production proof is complete.

- [ ] **Step 2: Run the complete targeted suite before PR**

Run:
`python -m pytest -q tests/test_cfb_game_total_v152_activation.py tests/test_cfb_game_total_v152_identity.py tests/test_cfb_game_total_v152_team_stats.py tests/test_cfb_game_total_v152_evidence_center.py tests/test_cfb_game_total_v152_layout.py tests/test_cfb_game_total_browser_v152.py tests/test_devsystem_production_verify_v3.py`
Expected: PASS with zero failures.

- [ ] **Step 3: Run repository gates**

Require CFB critical, regression shield, permanent contract, Monster Anti-Loop V2, browser QA, and DevSystem final gate to be GREEN on the PR head.

- [ ] **Step 4: Merge only the certified PR head into protected `main`**

Pin the expected head SHA during merge.

- [ ] **Step 5: Wait only on the post-merge V152 production checks**

Require production V3 verifier and production Game Total browser QA to prove the deployed site reports `CFB_GAME_TOTAL_V152_PRODUCTION_ACTIVE`, not merely HTTP 200.

- [ ] **Step 6: Record freeze evidence and close the task ledger**

Record final certified main SHA, rollback parent, production proof run IDs, and set task ledger status to `DONE`.

- [ ] **Step 7: Final anti-loop rule**

Once Step 8 is GREEN, stop polling/rechecking V152 unless a genuinely new production failure is observed.
