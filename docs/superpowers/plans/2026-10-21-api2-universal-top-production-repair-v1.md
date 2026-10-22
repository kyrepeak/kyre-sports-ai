# API2 Universal TOP Production Repair V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the universal `↑ TOP` control visible and usable on public Streamlit pages without depending on client scroll detection or JavaScript execution.

**Architecture:** Keep Universal Page Experience V1 as the single owner. Add a native fixed TOP fallback rendered by the universal runtime through ordinary Streamlit HTML/Markdown; let the existing client controller only enhance the same control. Do not alter sports data, projections, destination routing, or loader behavior.

**Tech Stack:** Python, Streamlit, HTML/CSS, pytest.

**Spec:** `docs/superpowers/specs/2026-10-21-api2-universal-top-production-repair-v1.md`

## Global Constraints

- One workstream, one branch, one PR, one Runless proof path.
- Preserve API2/Monster isolation.
- No SGO, ESPN, or ESPN BET changes; sports data routing is out of scope.
- No model/projection changes.
- TOP must work without JavaScript and without a Streamlit rerun.

## Review Focus

- Mobile Safari/Streamlit where the JS scroll owner is not the expected container.
- Streamlit versions where `st.html(..., unsafe_allow_javascript=True)` is unavailable and runtime falls back to an iframe.
- Duplicate TOP controls when both native fallback and JS enhancement are active.
- Fixed control safe-area placement on iPhone.
- Anchor action must not change sport/market route state.

---

### Task 1: Native universal TOP fallback

**Files:**
- Modify: `universal_page_experience_v1.py`
- Modify: `universal_page_experience_runtime_v1.py`
- Create: `tests/test_universal_top_production_repair_v1.py`

**Interfaces:**
- Produces: `page_experience_native_top_markup() -> str`
- Consumes: existing `page_experience_controller_markup(route)` and universal runtime mount path.

- [ ] Write a failing regression test proving the current code has no native fixed TOP fallback and requires the new exported helper/runtime mount.
- [ ] Run the focused test and confirm RED for the missing helper/native mount contract.
- [ ] Implement the smallest native fixed `↑ TOP` fallback with `href="#"`, mobile safe-area positioning, and no JS requirement.
- [ ] Mount the native fallback unconditionally through Streamlit Markdown/HTML before the JS enhancement; make the JS reuse it and never hide it.
- [ ] Run the focused test, the existing Universal Page Experience tests, and compile checks.
- [ ] Add proof-plan/ledger artifacts, submit one Runless proof, merge exact candidate only after authorization, then freeze/read back through the existing certified closeout path.