# API 2 — CFB Moneyline Premium V2

## Goal
Turn the current CFB Moneyline surface into a decision-first professional sports analytics page without changing the certified Moneyline engine, probabilities, fair-moneyline math, ranking, team identity, schedule truth, or sportsbook projection influence.

## Step 2A authority
- Workstream/branch: `api2-cfb-moneyline-premium-v2`
- Base main: `666408b952305daa94db1ac0c8bba258e7a812da`
- Scope lease: `SCOPE-LEASE-98974E1F59BA8D10CE58E11A`
- One branch, one PR, one exact-head Runless proof, one merge, one closeout.

## Architecture
1. `cfb_moneyline_clean_page_v2.py` is presentation-only and delegates all analysis to frozen V1/Step-5/Step-6 owners.
2. The first visible analytics surface is a Moneyline Decision card: pick/pass, model P(win), fair moneyline, grade/tier, reliability and coverage.
3. `WHY THIS PICK` translates existing frozen component deltas into football-language reasons; it does not recompute model probability.
4. Sportsbook prices are display-only and shown only if already attached as verified `sportsbook_moneylines`; missing data stays unavailable rather than fabricated. Model weight remains 0%.
5. Deep audit/model/team evidence remains available in human-facing collapsed sections.
6. `universal_runtime_v5_loader_v14.py` overrides only exact `CFB / moneyline`, while explicitly preserving V13 tap-only selectors and automatic next-slate date bridge.
7. Runtime V5 advances one loader import V13 -> V14. All other destinations delegate unchanged.

## Invariants
- `slate.analyze_game(game, selected_day)` remains the analysis boundary.
- `FROZEN_MONEYLINE_OWNER == cfb_moneyline_hub_v5`.
- `FROZEN_RAW_MODEL == cfb_moneyline_model_v1`.
- `FROZEN_FINAL_MODEL == cfb_moneyline_final_v1`.
- sportsbook projection influence remains exactly `0.0`.
- no fake pick, price, edge, probability or sportsbook quote.
- fail-closed output is presented as `PASS / NO QUALIFIED MODEL PICK`.
- no universal CFB keyboard/next-slate regression.

## TDD evidence
- Initial RED: 8/8 premium tests failed because V2/V14 did not exist and Runtime V5 still pointed to V13.
- GREEN after implementation: 8/8 passed.
- Universal-wrapper RED: dedicated V14 preservation test failed because the first override bypassed V13 contexts.
- Universal-wrapper GREEN: 9/9 passed after V14 explicitly reinstated tap-only + next-slate contexts.
- Regression: 92 passed, with one historical V13-only version-string assertion intentionally excluded because V14 is the additive successor; Runtime V5 cert remained GREEN.
