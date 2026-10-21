# NBA PRA No-ESPN Enrichment Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restore NBA player identity, history, projection, probability, and edge through Kyre Sports API without ESPN or SGO while preserving the working PRA sportsbook market path.

**Architecture:** Streamlit calls Kyre Sports API only. Kyre Sports API routes player enrichment by data type: NBA Official/NBA Stats first, then configured licensed providers, then Basketball-Reference for player identity/history when official data is degraded; each provider reports HEALTHY/DEGRADED/UNAVAILABLE and routing stops after sufficient verified data. Canonical Kyre player IDs are generated independently of provider IDs.

**Tech Stack:** Python, FastAPI, Streamlit, httpx/requests, pytest, Vercel Runless.

**Spec:** User-approved API 2 temporary ESPN removal / NBA multi-source routing contract in current chat.

## Global Constraints
- ESPN prohibited in active NBA path.
- SGO prohibited in active NBA path.
- Frontend never calls providers directly.
- Preserve sportsbook/provider/line/price/timestamp identity; never average lines.
- Never fabricate missing data.
- One branch, one PR, one exact SHA/deploy/proof path.

## Tasks
1. Add RED tests for no ESPN/SGO, canonical IDs, failover, history, projection, probability and edges.
2. Add `runless_v2/nba_pra_player_context_v1.py` with NBA Official -> configured licensed -> Basketball-Reference routing, health states, stable Kyre IDs and explicit DATA_UNAVAILABLE.
3. Add `nba_pra_player_context_api_v1.py`; modify Page 1 API overlay to consume player context only from Kyre Sports API.
4. Remove dormant SGO fallback from active `runless_v2/nba_pra_market_v1.py` while preserving the working FanDuel market feed.
5. Run focused/regression/compile checks, exact-head proof, merge, production read-back, closeout and freeze.
