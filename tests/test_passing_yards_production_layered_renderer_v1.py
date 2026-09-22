from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import nfl_passing_yards_hub_v43 as v43

captured = {
    "identity": ['<article>QB A LIVE</article>', '<article>QB B LIVE</article>'],
    "projection": ['<section>PROJ A</section>', '<section>PROJ B</section>'],
    "market": ['<section>MARKET A</section>', '<section>MARKET B</section>'],
    "profile": ['<section>PROFILE A</section>', '<section>PROFILE B</section>'],
    "defense": ['<section>DEF A</section>', '<section>DEF B</section>'],
    "pressure": ['<section>PRESS A</section>', '<section>PRESS B</section>'],
    "personnel": ['<section>PERSON A</section>', '<section>PERSON B</section>'],
    "environment": ['<section>ENV LIVE</section>'],
    "context": ['<section>CTX A</section>', '<section>CTX B</section>'],
    "distribution": ['<section>DIST A</section>', '<section>DIST B</section>'],
}
html = v43._layered_player_cards_html(captured)

assert 'data-live-passing-layered="true"' in html
assert html.count('data-live-qb-card=') == 2
assert "Passing Yards" in html
assert "QB A LIVE" in html and "QB B LIVE" in html
assert "PROJ A" in html and "MARKET B" in html
assert "PROFILE A" in html and "DEF B" in html
assert "Overview" in html and "Why" in html and "Matchup" in html
assert "Trends" in html and "Market" in html and "Deep Data" in html
assert "Open Full Breakdown" in html
assert "Combined Player Cards" not in html
assert "sportsbook projection influence" not in html.lower()
assert v43.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
assert v43.STAKE_SIZING_ENABLED is False
print("PASSING_YARDS_PRODUCTION_LAYERED_RENDERER_GREEN")
