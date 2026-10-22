from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]


def _load_path(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_api():
    import sports_api as pkg

    package = types.ModuleType("sports_api.api")
    package.__path__ = [str(ROOT / "sports_api" / "api")]
    package.__package__ = "sports_api.api"
    sys.modules["sports_api.api"] = package
    pkg.api = package
    return _load_path(
        "sports_api.api.cfb_top_picks_page1_v4",
        ROOT / "sports_api" / "api" / "cfb_top_picks_page1_v4.py",
    )


def test_ncaa_winning_percentage_parser_provides_record_and_official_logo():
    identity = _load_path(
        "sports_api.collectors.cfb_top_picks_identity_v1",
        ROOT / "sports_api" / "collectors" / "cfb_top_picks_identity_v1.py",
    )
    html = """
    <table><thead><tr><th>Rank</th><th>Team</th><th>W</th><th>L</th><th>T</th><th>Pct</th></tr></thead>
    <tbody><tr><td>7</td><td><img src="https://www.ncaa.com/sites/default/files/images/logos/schools/bgl/memphis.svg"><a href="/schools/memphis" class="school">Memphis</a></td><td>6</td><td>1</td><td>0</td><td>.857</td></tr></tbody></table>
    """
    rows = identity.parse_ncaa_winning_percentage_html(html)
    assert rows["memphis"]["record_text"] == "6-1"
    assert rows["memphis"]["logo_url"].endswith("/bgd/memphis.svg")
    assert rows["memphis"]["record_status"] == "VERIFIED"


def test_official_sidearm_roster_parser_extracts_current_player_identity():
    identity = _load_path(
        "sports_api.collectors.cfb_top_picks_identity_v1",
        ROOT / "sports_api" / "collectors" / "cfb_top_picks_identity_v1.py",
    )
    html = """
    <li data-test-id="roster-view-type-list__list-item">
      <a aria-label="Emory Williams jersey number 9 full bio" href="/sports/football/roster/emory-williams/14335" data-test-id="s-person-details__thumbnail-link">
        <img data-test-id="s-image-resized__img" src="https://img.example/emory.jpg">
      </a>
      <a href="/sports/football/roster/emory-williams/14335" data-test-id="s-person-details__personal-single-line-person-link">Emory Williams</a>
      <span data-test-id="s-person-details__bio-stats-person-position-short"><span class="sr-only">Position</span> QB</span>
      <span data-test-id="s-person-details__bio-stats-person-season"><span class="sr-only">Academic Year</span> Sr.</span>
    </li>
    """
    rows = identity.parse_official_roster_html(html, "https://ecupirates.com")
    player = rows["emory williams"]
    assert player["official_roster_id"] == "14335"
    assert player["jersey_number"] == "9"
    assert player["position"] == "QB"
    assert player["class_year"] == "Sr."
    assert player["headshot_url"] == "https://img.example/emory.jpg"
    assert player["profile_url"].startswith("https://ecupirates.com/")


def test_v4_enrichment_uses_verified_ncaa_team_identity_and_official_roster():
    api = _load_api()
    payload = {
        "selected_date": "2026-10-22",
        "slate_dates": ["2026-10-22"],
        "game_picks": [{
            "rank": 1, "event_id": "6603720", "away_team": "East Carolina", "home_team": "Memphis",
            "away_record": "6 GAME SAMPLE • W-L UNAVAILABLE", "home_record": "7 GAME SAMPLE • W-L UNAVAILABLE",
            "away_logo": None, "home_logo": None, "kickoff_iso": "2026-10-22T19:30:00-04:00",
        }],
        "player_props": [{
            "rank": 1, "event_id": "6603720", "player_name": "Emory Williams", "player_id": None,
            "away_team": "East Carolina", "home_team": "Memphis", "away_logo": None, "home_logo": None,
            "kickoff_iso": "2026-10-22T19:30:00-04:00",
        }],
        "routing": {}, "diagnostics": {},
    }
    events = {"6603720": {
        "away": {"name": "East Carolina", "slug": "east-carolina"},
        "home": {"name": "Memphis", "slug": "memphis"},
    }}
    teams = {
        "east-carolina": {"team_name": "East Carolina", "record_text": "5-2", "record_status": "VERIFIED", "logo_url": "https://www.ncaa.com/sites/default/files/images/logos/schools/bgd/east-carolina.svg"},
        "memphis": {"team_name": "Memphis", "record_text": "6-1", "record_status": "VERIFIED", "logo_url": "https://www.ncaa.com/sites/default/files/images/logos/schools/bgd/memphis.svg"},
    }
    rosters = {
        "east-carolina": {"emory williams": {"official_roster_id": "14335", "headshot_url": "https://img.example/emory.jpg", "position": "QB", "jersey_number": "9", "class_year": "Sr.", "profile_url": "https://ecupirates.com/sports/football/roster/emory-williams/14335", "identity_source": "Official team roster"}},
        "memphis": {},
    }
    out = api.enrich_page1_payload(payload, event_index=events, team_index=teams, roster_index=rosters)
    game = out["game_picks"][0]
    prop = out["player_props"][0]
    assert game["away_record"] == "5-2" and game["home_record"] == "6-1"
    assert game["away_logo"].endswith("east-carolina.svg") and game["home_logo"].endswith("memphis.svg")
    assert game["date_label"] == "TODAY"
    assert prop["player_team"] == "East Carolina"
    assert prop["opponent"] == "Memphis"
    assert prop["player_id_display"] == "14335"
    assert prop["player_headshot"] == "https://img.example/emory.jpg"
    assert prop["position"] == "QB" and prop["jersey_number"] == "9"
    assert prop["team_logo"].endswith("east-carolina.svg")
    assert prop["identity_status"] == "VERIFIED"


def test_v15_page1_is_simple_and_cannot_leak_indented_html():
    page = _load_path("cfb_top_picks_page_v15", ROOT / "cfb_top_picks_page_v15.py")
    source = (ROOT / "cfb_top_picks_page_v15.py").read_text(encoding="utf-8")
    folded = source.casefold()
    assert "why this pick" not in folded
    assert "id not reported" not in folded
    assert "w-l unavailable" not in folded
    assert "_clean_html" in source
    sample = page._clean_html("""\n    <section>\n      <div>OK</div>\n    </section>\n    """)
    assert sample.startswith("<section>")
    assert not any(line.startswith("    <") for line in sample.splitlines())


def test_v4_source_policy_forbids_legacy_provider_dependencies_and_requires_single_gateway():
    api_source = (ROOT / "sports_api" / "api" / "cfb_top_picks_page1_v4.py").read_text(encoding="utf-8").casefold()
    identity_source = (ROOT / "sports_api" / "collectors" / "cfb_top_picks_identity_v1.py").read_text(encoding="utf-8").casefold()
    page_source = (ROOT / "cfb_top_picks_page_v15.py").read_text(encoding="utf-8").casefold()
    assert "/api/v4/cfb/top-picks" in api_source
    assert "kyre sports api" in api_source
    assert "ncaa" in identity_source
    assert "official team roster" in identity_source
    assert "sportsgameodds" not in api_source + identity_source + page_source
    assert "espn.com" not in api_source + identity_source + page_source
    assert "espnapi" not in api_source + identity_source + page_source
