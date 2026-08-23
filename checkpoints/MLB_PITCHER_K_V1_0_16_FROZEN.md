# MLB Pitcher Strikeouts — Frozen Production Checkpoint

Status: **FROZEN / VERIFIED**
Version: **Pitcher K V1.0.16**
Frozen app commit: **050e5add6bd2c9e7a50cf83902870815c842222e**
Date verified: **2026-08-23**

## Verified production behavior

- Strongest Pitcher Strikeout O/U Top-5 board renders correctly.
- Top-5 ordering remains based on the existing model probability at the posted/entered line.
- Real sportsbook K lines are available through redundant transport:
  1. SportsGameOdds primary
  2. Odds-API.io fallback/gap fill
  3. Same-slate 15-minute last-good real-line cache
- No sportsbook line is fabricated.
- Existing projection math and Monte Carlo remain unchanged from the preserved Pitcher K model stack.
- Existing market grading remains unchanged.
- Existing team logos remain present.
- Top-5-only intelligence is rendered inside each ranked card:
  - Pick Strength
  - Matchup grade
  - Workload grade
  - Evidence score
  - Last 5 Ks
  - L5 line hit result
  - L10 line hit result
  - Pitcher vs opponent history
  - Recent H2H Ks
  - Opponent K environment
  - Supports
  - Concerns
- Supports/Concerns use the same evidence thresholds and fail safely per signal.
- Renderer-order collision is repaired so the V1.0.15 evidence-reason renderer remains active at Top-5 draw time.

## Verified screenshot example

Daniel Lynch IV card displayed:
- Rank 1
- Confirmed opponent lineup
- Over 2.5
- 88.5% model probability
- BetMGM market line/price
- Pick Strength: MEDIUM
- Matchup: MEDIUM
- Workload: NORMAL
- Evidence: 65/100
- Supports: Model • Matchup • Workload
- Concerns: L5 • L10 • H2H

## Freeze rule

Do not modify this checkpoint while building other markets. Future Pitcher K work must be additive through a new wrapper/version and must preserve V1.0.16 as the rollback point.

NFL Moneyline V1.8 remains independently frozen. Other MLB/WNBA production routes remain untouched by this checkpoint.
