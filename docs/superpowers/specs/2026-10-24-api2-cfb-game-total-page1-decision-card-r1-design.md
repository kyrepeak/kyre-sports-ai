# CFB Game Total Page 1 Decision Card R1 Design

## Intent
Make CFB Game Total Page 1 feel visually complete and S-tier while remaining a fast pregame decision surface. Keep Page 2 as the deep analytical destination.

## Chosen approach
Use one compact Decision Card for the selected matchup. Preserve the V5 horizontal logo rail. The selected card adds visible team logos on mobile, Market Total, Kyre Projected Total, Kyre model Over/Under probability, and one restrained MODEL TILT strip. Consensus, movement, prices, freshness, and Open Analysis remain secondary.

## Data ownership
Kyre Sports API remains the only application-facing data gateway. A new additive selected-game decision endpoint reuses the permanently frozen CFB Game Total model/slate owners. It does not alter model math, projection, probability, ranking, or selection. Sportsbook input remains 0.0 model weight. If the frozen model is unavailable, emit semantic MODEL_PENDING states; never substitute no-vig market probability as Kyre probability.

## Page boundaries
- Page 1: matchup identity, market total, Kyre projected total, Kyre O/U probability, model tilt, compact market context.
- Page 2: deep team profiles, trends, drivers, uncertainty, line lab, matchup research, and full decision detail.
- No Page 2 file may be modified.

## Mobile composition
Team logos remain visible in the selected matchup header at phone widths. Three primary metrics stay above the fold. Secondary price/consensus/movement content is visually quieter.

## Frozen constraints
- Do not modify `cfb_game_total_model_v1.py`.
- Do not modify `cfb_game_total_final_v1.py`.
- Do not modify `cfb_game_total_slate_v1.py`.
- `SPORTSBOOK_PROJECTION_INFLUENCE = 0.0`.
- No SGO, ESPN, or ESPN BET in routing/provider selection.
- Upcoming-only visibility remains unchanged.
