# MONSTER WNBA PRA Upcoming-Games-Only R1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prevent any WNBA game that has started, finished, or passed its certified tip time from entering PRA Page 1 cards, Top 3 rankings, or player-analysis handoff.

**Architecture:** Keep Kyre Sports API as the sole application-facing gateway. Add a narrow successor around the current WNBA PRA market bridge that filters the certified schedule before sportsbook offers are matched, then install that gate at the frozen V3.6.12 compatibility boundary.

**Tech Stack:** Python 3.11, Streamlit, Kyre Sports API schedule/market snapshots, pytest, Runless App 5204253.

## Global Constraints
- MONSTER only; API 2 state is not evidence.
- Base exactly `e319e5c73980736ca3e5da71316e018e025eb52c`.
- No ESPN, ESPN BET, SGO, Render, direct sportsbook frontend calls, or projection/model changes.
- Started/final games are never valid Page 1 inputs.
- A stale `scheduled` status cannot keep a game eligible after its certified tip time has passed.

## Acceptance
1. Live/final status is rejected.
2. Scheduled games whose certified tip time is at or before current time are rejected.
3. Unknown status fails closed unless a certified future tip proves the game is upcoming.
4. Provider offers for rejected games never enter `player_props`.
5. Page 1 compatibility hub installs the gate before rendering.
6. Existing market bridge/freshness/auto-slate tests remain green.
7. Exact candidate earns `runless-final-gate` from App 5204253 before merge.
8. Production read-back proves only upcoming games remain, then `MONSTER_WNBA_PRA_UPCOMING_ONLY_R1_FROZEN` is written/read back.
