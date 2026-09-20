# Sport Navigation Dropdown Category Contract V1

This contract freezes the **existing Streamlit categories only** for the sport-navigation dropdown project.

No category in this file is invented. Each value is copied from the current authoritative route owner.

## NFL

Owner: `streamlit_memory_lazy_router_v1.NFL_MARKETS`

- Slate
- Moneyline
- Spread
- Game Total
- Passing Yards
- Rushing Yards
- Receiving Yards
- Receptions
- Passing TDs
- Anytime TD
- Daily Picks

## CFB

Owner: `cfb_hub_v1.CFB_MARKETS` (inherited by the current CFB hub)

- Moneyline
- Over/Under
- Game Total

## MLB

Owner: `streamlit_memory_lazy_router_v1.MLB_MARKETS`

- Slate
- 1+ Hit
- 2+ Hits
- Home Run
- Hits + Runs + RBIs
- Pitcher Strikeouts
- Matchup Explorer
- Daily Game Picks
- Moneyline
- Run Line
- Game Total
- Live Game

## WNBA

Owner: `streamlit_memory_lazy_router_v1.WNBA_MARKETS`

- Points
- Rebounds
- Assists
- Rebounds + Assists
- PRA
- Spread
- Moneyline
- Game Total
- Daily Picks

## Guardrails

- Dropdown work must use these exact route values.
- Existing market/session routing remains authoritative.
- No display-only category may be added unless it already maps to one of these route values.
- Step 1 changes no UI, router behavior, data, or model logic.
