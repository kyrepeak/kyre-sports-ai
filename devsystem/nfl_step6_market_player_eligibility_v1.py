"""Targeted Step 6 proof: all runtime NFL player-prop market owners use the shared eligibility gate."""
from pathlib import Path

TARGETS = (
    "sports_api/collectors/nfl_passing_yards_render_espn_v2.py",
    "sports_api/collectors/nfl_fanduel_rushing_yards_v2.py",
    "sports_api/collectors/nfl_fanduel_receiving_yards_v1.py",
)

for target in TARGETS:
    text = Path(target).read_text(encoding="utf-8")
    assert "nfl_prop_market_eligibility_v1 as market_elig" in text, target
    assert "market_elig.build_event_market_eligibility(" in text, target
    assert "market_elig.market_row_eligible(" in text, target

frozen = Path("sports_api/collectors/nfl_fanduel_rushing_yards_v1.py").read_text(encoding="utf-8")
assert "nfl_prop_market_eligibility_v1 as market_elig" not in frozen

print("NFL_STEP6_MARKET_PLAYER_ELIGIBILITY_GREEN")
