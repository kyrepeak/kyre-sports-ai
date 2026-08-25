# WNBA PRA Precision Step 1 — Opportunity Decomposition

Date: 2026-08-25

## Frozen production boundary

This checkpoint branches after the verified PRA V3.6.12 Step-5 presentation
baseline. The underlying V3.6.11/V3.6.2/V3.6.1 production chain remains
authoritative.

## Step 1 adds

- Read-only opportunity decomposition directly beneath the existing V2.8
  Minutes + Role PRA Top-5.
- Projected minutes beside season/L10/L5 minutes.
- Existing separate projected PTS, REB, AST and combined PRA.
- Season/L10/L5 PTS/REB/AST per-36 opportunity rates.
- Existing projected usage beside available season/L10/L5 Advanced USG.
- Starter/rotation status and deterministic sample-reliability label.
- Explicit UNAVAILABLE labels for potential assists, rebound chances and touches
  when a verified tracking source is not present.

## Hard contracts

Step 1 does NOT change:
- projected minutes or usage;
- PTS, REB, AST or PRA projection math;
- sportsbook transport or exact market pairing;
- 5M/10M Monte Carlo;
- fair odds, no-vig edge or EV;
- qualification or production grade;
- Top-5 membership, ranking or order;
- injury, lineup, matchup or calibration logic.

No new provider is fetched by this presentation layer. It reuses the V2.8
player-form and Advanced usage data already in the PRA chain.
