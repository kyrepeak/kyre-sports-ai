# MLB Spread Step 1 — Frozen Checkpoint

Date: 2026-08-24

Frozen runtime checkpoint: `2ffc1c6d7cb05551a166e508a02d5cf040843488`

## Verified Step 1 scope

Today's Strongest Spread Projections now includes:

- selected-team and opponent MLB logos;
- display-only Pick Strength and Probability Strength;
- existing V15.2 history-adjusted cover probability and fair odds;
- H2H last-10 record;
- last-5 H2H record;
- weighted average H2H score and margin;
- current-season H2H;
- current-venue H2H;
- one-run H2H rate;
- H2H sample reliability;
- last-five completed regular-season H2H ledger with official schedule dates, score, W/L, margin and replay result against today's selected +/-1.5 line.

## H2H intake repairs verified before freeze

1. Replaced stale/incomplete multi-season schedule intake with newest-first season-segmented MLB StatsAPI history.
2. Uses official schedule date instead of UTC `gameDate` date slicing, preventing local-night games from shifting to the following date.
3. Includes completed regular-season MLB games only (`gameType = R`), excluding Spring Training, split-squad and exhibition games.
4. Deduplicates by MLB `gamePk` and sorts newest to oldest.
5. Converts every history row to the currently selected spread team's perspective.
6. Old saved scans are invalidated after source/date-filter changes so history-adjusted probabilities are rebuilt from corrected history.

## Protected production behavior

Do not change as part of Step-1 presentation work:

- V15.2 core run model;
- Monte Carlo simulation;
- projected scores;
- V15.2 H2H weighting/shrinkage formula;
- +/-5 percentage-point total history-adjustment cap;
- convergence rules;
- fair-odds math;
- data-confidence logic;
- Top-5 ranking order;
- V15.3 backtest;
- V15.4 live board;
- V15.5 verified-slate intake.

Pick Strength and Probability Strength remain display-only and must not qualify, filter or rerank production selections.

## Visual verification example

San Francisco Giants +1.5 vs Cincinnati Reds showed:

- Pick Strength: ELITE
- Probability Strength: VERY HIGH
- History-adjusted cover: 68.2%
- Core cover: 64.2%
- History adjustment: +4.0 pp
- H2H L10: 5-5
- Current-season H2H: 1-2
- Last five completed regular-season meetings displayed as:
  - Apr 16, 2026
  - Apr 15, 2026
  - Apr 14, 2026
  - Apr 09, 2025
  - Apr 08, 2025

This is the rollback point before MLB Spread Card Step 2.
