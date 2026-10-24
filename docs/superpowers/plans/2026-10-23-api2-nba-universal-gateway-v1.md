# API2 NBA Universal Gateway V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Kyre Sports API the sole application-facing NBA gateway, migrate all current NBA PRA product routes to it, and establish a reusable NBA domain for future pages.

**Architecture:** Add a first-class `/api/v1/nba` domain router plus product-serving PRA routers under `sports_api/api/`. Preserve the current PRA contracts while repointing every NBA application client from Runless to `https://kyre-sports-api.vercel.app`; Runless remains proof/control plane only.

**Tech Stack:** Python, FastAPI, Pydantic, httpx/requests, pytest, Vercel, Runless V2.

**Spec:** `docs/superpowers/specs/2026-10-23-api2-nba-universal-gateway-v1-design.md`

## Global Constraints
- Kyre Sports API is the ONLY application-facing NBA API/data gateway.
- Do NOT use SGO / SportsGameOdds.
- Do NOT use ESPN.
- Do NOT use ESPN BET.
- No fabricated numeric data.
- Sportsbook observations have 0.0 projection influence and no consensus averaging.
- Runless is verification/control plane only.
- Keep unrelated sports/runtime behavior unchanged.

## Review Focus
- A future NBA page must have one obvious `/api/v1/nba/*` extension point rather than a new host.
- A client environment override may change host, but the default must never fall back to Runless.
- FanDuel singular/plural/full PRA market labels must normalize identically while ALT markets remain excluded.
- Existing CFB/NFL routes in the Vercel entrypoint must remain registered.
- Missing provider data must remain semantic unavailable rather than zero/fabricated.

---

### Task 1: Architecture RED gate

**Files:**
- Create: `tests/test_api2_nba_universal_gateway_v1.py`
- Create: `devsystem/task_ledgers/api2-nba-universal-gateway-v1.json`
- Create: `devsystem/runless_proof_plans/api2-nba-universal-gateway-v1.json`

**Interfaces:**
- Consumes: current main `8f5a718dba602f7fa49e24daa1a8c8946e81d486`.
- Produces: failing tests defining NBA host ownership, route registration, domain manifest, and FanDuel PRA normalization.

- [ ] Write tests asserting all five NBA application clients default to `https://kyre-sports-api.vercel.app` and contain no Runless production host.
- [ ] Write TestClient/OpenAPI assertions for `/api/v1/nba/status` and all five current PRA routes.
- [ ] Write parser tests for `Pts + Reb + Ast`, `Pts + Rebs + Asts`, and `Points + Rebounds + Assists`, and ensure ALT markets are excluded.
- [ ] Run exact candidate proof and record the expected RED failure before product code exists.

### Task 2: NBA domain and PRA product routers

**Files:**
- Create: `sports_api/api/nba_gateway_v1.py`
- Create: `sports_api/api/nba_pra_market_v1.py`
- Create by product-code migration: `sports_api/api/nba_pra_schedule_v1.py`
- Create by product-code migration: `sports_api/api/nba_pra_player_context_v1.py`
- Create by product-code migration: `sports_api/api/nba_pra_injury_v1.py`
- Create by product-code migration: `sports_api/api/nba_pra_matchup_v1.py`

**Interfaces:**
- Produces: FastAPI routers for the NBA domain and all currently used PRA product data.
- Preserves: existing route paths and response contracts.

- [ ] Add `/api/v1/nba/status` manifest with Kyre-only ownership and future market capability contract.
- [ ] Move/copy current schedule, player-context, injury and matchup product route implementations into `sports_api/api/` without Runless imports.
- [ ] Implement PRA market router with robust market-name normalization and existing observation contract.
- [ ] Verify banned-provider strings are absent from the active Kyre NBA route modules.

### Task 3: Register NBA on Kyre Sports API and migrate application clients

**Files:**
- Modify: `kyre_sports_api_vercel_v1.py`
- Modify: `nba_pra_market_api_v1.py`
- Modify: `nba_pra_schedule_api_v1.py`
- Modify: `nba_pra_player_context_api_v1.py`
- Modify: `nba_pra_injury_api_v1.py`
- Modify: `nba_pra_page2_matchup_api_v1.py`

**Interfaces:**
- Consumes: Task 2 routers.
- Produces: one production NBA application host: `https://kyre-sports-api.vercel.app`.

- [ ] Register NBA domain + five PRA routers in the Vercel FastAPI app.
- [ ] Repoint all five application-client defaults to the Kyre Sports API host while preserving `KYRE_NBA_API_BASE_URL` overrides.
- [ ] Add NBA capability flags to `/health` without removing existing CFB/NFL flags.
- [ ] Run focused test suite to GREEN.

### Task 4: Exact-head proof, merge, production proof, freeze

**Files:**
- Update: `devsystem/task_ledgers/api2-nba-universal-gateway-v1.json`

**Interfaces:**
- Consumes: exact candidate head from Tasks 1–3.
- Produces: Runless gate, merged main SHA, production proof, frozen receipt.

- [ ] Run exact-head Runless proof: compile + focused NBA gateway tests + existing NBA gateway/no-ESPN regression tests.
- [ ] Require `failure_class = NONE` and `runless-final-gate` success on the exact head.
- [ ] Merge the one authoritative PR using expected-head protection.
- [ ] Verify exact production deployment is READY.
- [ ] Verify production `/api/v1/nba/status` is served by Kyre Sports API and contains `runless_product_transport=false`.
- [ ] Verify production PRA route is on the Kyre host and returns canonical JSON/semantic unavailable without fabrication.
- [ ] Finalize Runless freeze token `API2_NBA_UNIVERSAL_GATEWAY_V1_FROZEN` to `GREEN_FROZEN`.
- [ ] Release `SCOPE-LEASE-69DB65E03D56565E7DBE0185` and read back no matching live holder.
