# NFL Moneyline V1.8 — Frozen Production Checkpoint

Frozen on: 2026-08-23

Production entrypoint commit at freeze: `5768efcb6f5112560ba1ef6e95b2d9cf31b04edc`

## Frozen production route
- `app.py` -> `nfl_hub_v18`
- `nfl_hub_v18.py` -> `nfl_moneyline_hub_v8.py` for Moneyline

## Verified pipeline
1. Verified NFL slate
2. QB depth + current injury/availability
3. Preseason game-plan/QB-rotation safety gate
4A. Historical team-strength baseline
4B. Opponent + home-field context
4C. Historical calibrated base P(win)
5. Sportsbook Moneyline / same-book no-vig market
6. 5,000,000-draw Monte Carlo uncertainty
7. Model-vs-market no-vig edge + EV diagnostics
8. Final Decision grading layer

## Frozen behavior
- Step 3 is a mandatory preseason final-output veto gate.
- Regular-season games do not require the preseason rotation gate.
- Sportsbook prices never feed back into Step 4C or Step 6 model probabilities.
- Final grading evaluates hard eligibility gates before edge/EV thresholds.
- MLB and WNBA routes are outside this NFL checkpoint and must not be changed by future NFL work.

## Freeze rule
Do not edit `nfl_hub_v18.py` or `nfl_moneyline_hub_v8.py` for new NFL Moneyline development. Future NFL Moneyline changes must branch into a new wrapper/version after V1.8 so this checkpoint remains recoverable.
