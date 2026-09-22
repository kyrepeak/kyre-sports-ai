# WNBA Live Games V1 — Step 1 Frozen Checkpoint

Date verified: 2026-08-24 ET

Runtime commit before freeze: `33788bfef0ae1017b7bf7a0896ccc50f06618e84`

## Verified scope

WNBA → Live Games now routes to the isolated `wnba_live_hub_v1.py` Step-1 live-state page.

Step 1 is state-only. It does not include live sportsbook prices, projections, probabilities, Monte Carlo, EV, qualification, or picks.

## Verified live-card behavior

A mobile Streamlit screenshot verified a real in-progress game card for Golden State Valkyries at Minnesota Lynx with:

- VERIFIED LIVE STATE badge;
- state-change indicator;
- both WNBA team logos;
- current score;
- current quarter and game clock;
- quarter-by-quarter scoring;
- venue;
- state snapshot timestamp;
- last observed state-change timestamp;
- ESPN event ID;
- reconciled WNBA/ESPN slate verification.

Observed state at capture:

- Golden State 52 — Minnesota 44;
- Q3, 2:17 remaining;
- Q1: GS 17, MIN 16;
- Q2: GS 17, MIN 16;
- Q3: GS 18, MIN 12;
- venue: Target Center, Minneapolis, MN;
- event ID: 401857171;
- snapshot: 9:32:33 PM ET;
- slate verification: reconciled WNBA/ESPN consensus.

The quarter totals reconcile exactly to the displayed score: GS 17+17+18=52 and MIN 16+16+12=44.

## Protected behavior

Do not change as part of subsequent live-market work:

- verified WNBA selected-date slate reconciliation;
- WNBA-only team identity guard;
- live-state fail-closed reconciliation;
- current score / period / clock parsing;
- quarter-by-quarter score parsing;
- venue and event-ID display;
- state snapshot and last-change tracking;
- manual refresh control until a later refresh cadence is intentionally introduced.

Any future sportsbook market layer must consume this verified state boundary and must not overwrite or silently bypass it.

## Next build step

Step 2: add live sportsbook market intake for Moneyline, Spread, and Game Total as a separate layer over this frozen verified game-state foundation. Do not add model probabilities or picks until exact live-market identity, timestamps, pairing, freshness, and settlement semantics are verified.
