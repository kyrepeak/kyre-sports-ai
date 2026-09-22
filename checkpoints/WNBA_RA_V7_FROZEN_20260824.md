# WNBA Rebounds + Assists — Frozen Production Checkpoint

Status: **FROZEN / VERIFIED**
Version: **WNBA Rebounds + Assists V7**
Frozen app commit: **5b0165b3b1cad652edfb98fc12e6836931fa66b2**
Date verified: **2026-08-24**

## Verified production behavior

- WNBA navigation includes a dedicated **Rebounds + Assists** page isolated from Points, Rebounds, Assists, PRA, Spread, Moneyline, Game Total, Daily Picks, MLB and NFL routes.
- Step 1 verified player identity renders correctly with ESPN player photo, team/opponent logos, current roster identity, season/L10/L5 R+A, season REB/AST, minutes and games.
- Step 2 uses only the true combined `rebounds+assists` full-game sportsbook market.
- Separate rebound and assist props are never added together to fabricate an R+A line.
- Exact same-book + same-line Over/Under pairing is required for no-vig calculations.
- Step 3 renders current-team completed-game history strictly before the selected slate, including season/L10/L5 R+A, exact-line hit rates, home/away splits, H2H history, sample reliability and a Last-5 game-by-game REB/AST/R+A ledger.
- Step 4 renders read-only role/opportunity/matchup context including minutes trend, R+A per-36, rebound/assist share proxies, pace, assist environment, missed-field-goal/rebound environment and availability context.
- Step 4 does not invent official potential-assist or rebound-chance tracking when that data is unavailable; box-score proxy fields are explicitly labeled.
- Step 5 projects rebounds and assists separately, then combines them through a correlated 5,000,000-draw Monte Carlo distribution.
- Sportsbook line/price does not influence the statistical projection.
- Historical REB/AST correlation is sample-shrunk toward zero before covariance is simulated.
- Standard Monte Carlo run is exactly **5,000,000 draws** in deterministic 250,000-draw batches and reports actual simulations, seed, batches, MC standard error, max batch difference, convergence, mean, median, mode, P10/P90, fair odds and push probability.
- Step-5 mobile control repair is active so the 5M run button is available directly below the long player card.
- Step 6 applies sportsbook/no-vig/EV logic only after the completed Step-5 distribution.
- Step 6 requires verified/fresh exact market data, eligible model data/history/minutes, convergence, probability floor, no-vig edge floor and EV floor before a side can qualify.
- Step 6 keeps at most one strongest exact market per player and never forces five picks.
- Step 7 consumes only the saved Step-6 qualified board and does not rerun or alter projection, Monte Carlo, edge, EV, qualification, grade or rank.
- Step 7 final daily cards render player photo, both team logos, exact side/line/book/price, 5M probability, fair odds, projected R+A, no-vig market, edge, EV, projected REB/AST, minutes, model data, quote age, push, simulations, Last 5, reason why, supporting signals, concerns/variance and display confidence.
- Step 7 narrative is explanatory/presentation-only and is not fed back into the model.

## Verified screenshot example

Nneka Ogwumike final card displayed:
- Rank 1
- Grade: ELITE
- Display Confidence: VERY HIGH
- Los Angeles Sparks vs Atlanta Dream
- Over R+A 9.5
- FanDuel -108
- 74.7% 5M Over probability
- Fair odds -295
- Projected R+A 11.5
- 2.0 directional cushion
- No-vig market 49.6%
- No-vig edge +25.1 pp
- Push-aware EV 43.9%
- Player photo and both team logos rendered correctly

Step 6 also verified **5 production-qualified R+A player picks** on the tested market snapshot without forcing additional picks.

## Frozen route chain

`wnba_ra_hub_v1.py` → `wnba_ra_hub_v7.py` → V6 qualification → V5.1 control repair → V5 projection/5M MC → verified prior Steps 1–4.

## Freeze rule

Do not modify this checkpoint while building the next feature/market. Future WNBA R+A work must be additive through a new wrapper/version and must preserve **V7 / commit 5b0165b3b1cad652edfb98fc12e6836931fa66b2** as the rollback point.

Any future change to WNBA R+A must not silently alter the frozen projection math, correlated 5M Monte Carlo, exact-market verification, qualification thresholds, ranking behavior or final card values unless the user explicitly chooses to create a new post-V7 model version.
