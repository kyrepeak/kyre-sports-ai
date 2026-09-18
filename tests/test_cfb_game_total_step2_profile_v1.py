from __future__ import annotations

import json

import cfb_game_total_step2_profile_v1 as step2
import cfb_game_total_step2_drive_v1 as step2_drive


def _identity(away_team="Miami (FL)", home_team="Wake Forest"):
    return {
        "away": {
            "team": away_team,
            "logo": "https://a.espncdn.com/i/teamlogos/ncaa/500/2390.png",
        },
        "home": {
            "team": home_team,
            "logo": "https://a.espncdn.com/i/teamlogos/ncaa/500/154.png",
        },
    }


def _full(team: str, *, side: str, record: str, ppg: float, allowed: float):
    return {
        "side": side,
        "team": team,
        "conference": "ACC",
        "division_context": "FBS",
        "record_text": record,
        "record": {
            "wins": int(record.split("-")[0]),
            "losses": int(record.split("-")[1]),
            "games": sum(int(x) for x in record.split("-")[:2]),
        },
        "ppg": ppg,
        "points_allowed_pg": allowed,
        "point_diff_pg": ppg - allowed,
        "yards_per_play": 6.8 if side == "away" else 5.6,
        "yards_per_play_allowed": 5.0 if side == "away" else 6.2,
        "points_per_drive": 2.94 if side == "away" else 2.08,
        "points_per_drive_allowed": 1.58 if side == "away" else 2.36,
        "off_eff_rank": 12 if side == "away" else 58,
        "def_eff_rank": 24 if side == "away" else 79,
        "home_point_diff_pg": 18.0,
        "away_point_diff_pg": -6.0,
        "recent_form": "W-W" if side == "away" else "L-W",
        "completed_games": [{"event_id": "1"}, {"event_id": "2"}],
    }


def _away():
    return _full(
        "Miami (FL)",
        side="away",
        record="2-0",
        ppg=42.5,
        allowed=18.0,
    )


def _home():
    return _full(
        "Wake Forest",
        side="home",
        record="1-1",
        ppg=28.0,
        allowed=31.5,
    )


def test_step2_contract_is_presentation_only():
    assert step2.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert step2.MAY_MODIFY_PROJECTION is False
    assert step2.STEP2_REQUIRED_FIELDS == (
        "team",
        "record",
        "sample_games",
        "ppg",
        "allowed_pg",
        "point_diff_pg",
    )
    assert "recent_form" in step2.STEP2_ADVANCED_FIELDS
    assert "points_per_drive" in step2.STEP2_ADVANCED_FIELDS
    assert "yards_per_play" in step2.STEP2_ADVANCED_FIELDS


def test_step2_full_pair_is_ready_and_has_universal_insights():
    contract = step2.build_step2_contract(_identity(), _away(), _home())
    assert contract["state"] == "READY"
    assert contract["ready"] is True
    assert contract["away"]["record"] == "2-0"
    assert contract["home"]["record"] == "1-1"
    assert contract["away"]["sample_games"] == 2
    assert contract["away"]["split_summary"] == "Away -6.0"
    assert contract["home"]["split_summary"] == "Home +18.0"
    assert contract["away"]["offense_label"]
    assert contract["home"]["defense_label"]
    labels = [row["label"] for row in contract["insights"]]
    assert labels == [
        "Who scores more",
        "Who gives up more",
        "Who is more efficient",
        "Best profile edge",
    ]
    assert "Miami (FL)" in contract["summary"]


def test_step2_advanced_gaps_fail_closed_to_check_not_fake_ready():
    away = _away()
    home = _home()
    for key in (
        "yards_per_play",
        "yards_per_play_allowed",
        "points_per_drive",
        "points_per_drive_allowed",
        "off_eff_rank",
        "def_eff_rank",
    ):
        away.pop(key, None)
        home.pop(key, None)
    contract = step2.build_step2_contract(_identity(), away, home)
    assert contract["state"] == "CHECK"
    assert contract["ready"] is False
    assert "points_per_drive" in contract["away"]["missing_advanced"]
    assert contract["away"]["required_complete"] is True


def test_step2_missing_recent_form_fails_closed_to_check_not_data_limited():
    away = _away()
    away["recent_form"] = ""
    contract = step2.build_step2_contract(_identity(), away, _home())
    assert contract["state"] == "CHECK"
    assert "recent_form" in contract["away"]["missing_advanced"]
    assert contract["away"]["required_complete"] is True


def test_step2_missing_core_scoring_field_is_data_limited():
    away = _away()
    away["ppg"] = None
    contract = step2.build_step2_contract(_identity(), away, _home())
    assert contract["state"] == "DATA LIMITED"
    assert "ppg" in contract["away"]["missing_required"]


def test_step2_can_derive_ypp_and_rank_from_official_ncaa_rows():
    evidence = {
        "side": "away",
        "team": "Example State",
        "conference": "TEST",
        "division_context": "FBS",
        "record_text": "3-0",
        "record": {"wins": 3, "losses": 0, "games": 3},
        "ppg": 34.0,
        "points_allowed_pg": 17.0,
        "point_diff_pg": 17.0,
        "recent_form": "W-W-W",
        "away_record": {"wins": 1, "losses": 0, "games": 1},
        "official_stats": {
            "total_offense": {
                "headers": ["Rank", "Team", "G", "Plays", "Yards", "Yards/Game"],
                "row": ["14", "Example State", "3", "210", "1260", "420.0"],
            },
            "total_defense": {
                "headers": ["Rank", "Team", "G", "Plays", "Yards", "Yards/Game"],
                "row": ["22", "Example State", "3", "198", "990", "330.0"],
            },
            "scoring_offense": {
                "headers": ["Rank", "Team", "G", "PPG"],
                "row": ["9", "Example State", "3", "34.0"],
            },
            "scoring_defense": {
                "headers": ["Rank", "Team", "G", "PPG"],
                "row": ["18", "Example State", "3", "17.0"],
            },
        },
    }
    row = step2.build_team_profile_contract(
        evidence,
        {"team": "Example State", "logo": "https://example.test/logo.png"},
        side="away",
    )
    assert round(row["yards_per_play"], 2) == 6.0
    assert round(row["yards_per_play_allowed"], 2) == 5.0
    assert row["off_eff_rank"] == 9
    assert row["def_eff_rank"] == 18


def test_step2_render_matches_locked_neon_performance_profile_structure():
    html = step2.render_step2_html("CHECK", _identity(), _away(), _home())
    assert '<details class="gt159-step gt167-step2 ready"' in html
    assert 'data-testid="gt157-step-2"' in html
    assert 'data-step2-state="READY"' in html
    assert "Team Performance Profile" in html
    assert "Record • PPG • Allowed • Yards/Play • Pts/Drive • Efficiency • Point Diff • Splits • Recent Form" in html
    assert 'data-testid="gt167-step2-away"' in html
    assert 'data-testid="gt167-step2-home"' in html
    assert 'data-testid="gt167-step2-insights"' in html
    assert 'data-testid="gt167-step2-summary"' in html
    assert "WHAT STEP 2 TELLS YOU" in html
    assert "STEP 2 SUMMARY" in html
    assert "PROFILE EDGE" in html
    assert "Pts / Drive" in html
    assert "Yards / Play" in html
    assert "Off Eff Rank" in html
    assert "Def Eff Rank" in html
    assert "Miami (FL)" in html
    assert "Wake Forest" in html
    assert "42.5" in html
    assert "31.5" in html


def test_step2_is_not_hardcoded_to_mockup_matchup():
    identity = _identity("Oregon", "Penn State")
    away = _full("Oregon", side="away", record="4-0", ppg=38.2, allowed=15.7)
    home = _full("Penn State", side="home", record="3-1", ppg=30.4, allowed=19.1)
    html = step2.render_step2_html("CHECK", identity, away, home)
    assert "Oregon" in html
    assert "Penn State" in html
    assert "Miami (FL)" not in html
    assert "Wake Forest" not in html


def test_step2_css_keeps_mockup_style_and_responsive_layout():
    assert ".gt167-step2:before" in step2.STEP2_CSS
    assert "linear-gradient(90deg,#6cff45,#00f5ff,#8f59ff,#ff2bd6,#ffd93d,#57ff7a)" in step2.STEP2_CSS
    assert ".gt167-team-pair{display:grid" in step2.STEP2_CSS
    assert ".gt167-metrics{display:grid;grid-template-columns:repeat(4" in step2.STEP2_CSS
    assert "@media(max-width:760px)" in step2.STEP2_CSS



def test_step2_uses_verified_ncaa_scoring_rows_when_completed_sample_is_empty():
    evidence = {
        "side": "away",
        "team": "Coastal Carolina",
        "conference": "Sun Belt",
        "division_context": "FBS",
        "record_text": "2-1",
        "record": "2-1",
        "recent_form": "",
        "official_stats": {
            "scoring_offense": {
                "label": "NCAA Scoring Offense",
                "value": "31.3",
                "value_numeric": 31.3,
                "headers": ["Rank", "Team", "G", "PPG"],
                "row": ["44", "Coastal Carolina", "3", "31.3"],
            },
            "scoring_defense": {
                "label": "NCAA Scoring Defense",
                "value": "22.0",
                "value_numeric": 22.0,
                "headers": ["Rank", "Team", "G", "PPG"],
                "row": ["51", "Coastal Carolina", "3", "22.0"],
            },
        },
    }
    row = step2.build_team_profile_contract(
        evidence,
        {"team": "Coastal Carolina", "logo": "https://example.test/324.png"},
        side="away",
    )
    assert row["ppg"] == 31.3
    assert row["allowed_pg"] == 22.0
    assert round(row["point_diff_pg"], 1) == 9.3
    assert row["sample_games"] == 3
    assert row["required_complete"] is True
    assert row["state"] == "CHECK"


def test_step2_drive_table_parser_reads_offense_and_defense():
    off_html = """
    <div>1. Coastal Carolina : 2.58 pts/drive (offense)</div>
    <div>2. Delaware : 3.05 pts/drive (offense)</div>
    """
    def_html = """
    <div>1. Coastal Carolina : 1.73 pts/drive (defense)</div>
    <div>2. Delaware : 1.75 pts/drive (defense)</div>
    """
    offense = step2_drive._parse_ppd_table(off_html, "offense")
    defense = step2_drive._parse_ppd_table(def_html, "defense")
    assert offense["coastalcarolina"] == 2.58
    assert offense["delaware"] == 3.05
    assert defense["coastalcarolina"] == 1.73
    assert defense["delaware"] == 1.75


def test_step2_drive_enrichment_fills_only_missing_metrics(monkeypatch):
    tables = {
        "offense": {"coastalcarolina": 2.58, "delaware": 3.05},
        "defense": {"coastalcarolina": 1.73, "delaware": 1.75},
    }
    monkeypatch.setattr(
        step2_drive,
        "_fetch_snapshot_tables",
        lambda season: (
            tables["offense"],
            tables["defense"],
            {"delivery": "checked_in_snapshot"},
        ),
    )
    away, home, diag = step2_drive.enrich_step2_drive_metrics(
        {"team": "Coastal Carolina"},
        {"team": "Delaware"},
        2026,
    )
    assert away["points_per_drive"] == 2.58
    assert away["points_per_drive_allowed"] == 1.73
    assert home["points_per_drive"] == 3.05
    assert home["points_per_drive_allowed"] == 1.75
    assert away["step2_drive_source"] == "Punt & Rally"
    assert home["step2_drive_source"] == "Punt & Rally"
    assert diag["status"] == "READY"


def test_step2_drive_enrichment_preserves_existing_verified_metrics(monkeypatch):
    tables = {
        "offense": {"coastalcarolina": 2.58, "delaware": 3.05},
        "defense": {"coastalcarolina": 1.73, "delaware": 1.75},
    }
    monkeypatch.setattr(
        step2_drive,
        "_fetch_ppd_table",
        lambda season, stat: tables[stat],
    )
    away, home, diag = step2_drive.enrich_step2_drive_metrics(
        {
            "team": "Coastal Carolina",
            "points_per_drive": 9.99,
            "points_per_drive_allowed": 8.88,
        },
        {"team": "Delaware"},
        2026,
    )
    assert away["points_per_drive"] == 9.99
    assert away["points_per_drive_allowed"] == 8.88
    assert home["points_per_drive"] == 3.05
    assert home["points_per_drive_allowed"] == 1.75
    assert diag["status"] == "READY"


def test_step2_drive_enrichment_fails_closed_when_all_delivery_paths_fail(monkeypatch):
    monkeypatch.setattr(
        step2_drive,
        "_fetch_snapshot_tables",
        lambda season: (_ for _ in ()).throw(
            RuntimeError("snapshot unavailable")
        ),
    )
    monkeypatch.setattr(
        step2_drive,
        "_fetch_ppd_table",
        lambda season, stat: (_ for _ in ()).throw(
            RuntimeError("source unavailable")
        ),
    )
    away_in = {"team": "Coastal Carolina"}
    home_in = {"team": "Delaware"}
    away, home, diag = step2_drive.enrich_step2_drive_metrics(
        away_in,
        home_in,
        2026,
    )
    assert away == away_in
    assert home == home_in
    assert diag["status"] == "CHECK"
    assert "snapshot unavailable" in diag["error"]
    assert "source unavailable" in diag["error"]


def test_step2_checked_in_drive_snapshot_has_universal_2026_coverage():
    payload = json.loads(
        step2_drive.LOCAL_SNAPSHOT_PATH.read_text(encoding="utf-8")
    )
    offense, defense, diag = step2_drive._snapshot_tables_from_payload(
        payload,
        2026,
    )
    assert len(offense) == 138
    assert len(defense) == 138
    assert offense["coastalcarolina"] == 2.58
    assert defense["coastalcarolina"] == 1.73
    assert offense["delaware"] == 3.05
    assert defense["delaware"] == 1.75
    assert diag["snapshot_team_count"] == 138


def test_step2_drive_enrichment_prefers_snapshot_before_direct_upstream(monkeypatch):
    monkeypatch.setattr(
        step2_drive,
        "_fetch_snapshot_tables",
        lambda season: (
            {"coastalcarolina": 2.58, "delaware": 3.05},
            {"coastalcarolina": 1.73, "delaware": 1.75},
            {"delivery": "github_raw_snapshot"},
        ),
    )
    monkeypatch.setattr(
        step2_drive,
        "_fetch_ppd_table",
        lambda season, stat: (_ for _ in ()).throw(
            AssertionError("direct upstream should not run")
        ),
    )
    away, home, diag = step2_drive.enrich_step2_drive_metrics(
        {"team": "Coastal Carolina"},
        {"team": "Delaware"},
        2026,
    )
    assert away["points_per_drive"] == 2.58
    assert away["points_per_drive_allowed"] == 1.73
    assert home["points_per_drive"] == 3.05
    assert home["points_per_drive_allowed"] == 1.75
    assert diag["delivery"] == "github_raw_snapshot"
    assert diag["status"] == "READY"


def test_step2_split_summary_derives_from_verified_completed_game_locations():
    away_evidence = {
        "team": "Coastal Carolina",
        "record": "1-1",
        "ppg": 34.5,
        "points_allowed_pg": 19.0,
        "point_diff_pg": 15.5,
        "recent_form": "LW",
        "completed_games": [
            {"location": "away", "result": "L", "points_for": 24, "points_against": 31},
            {"location": "home", "result": "W", "points_for": 45, "points_against": 7},
        ],
    }
    home_evidence = {
        "team": "Delaware",
        "record": "1-1",
        "ppg": 34.0,
        "points_allowed_pg": 21.0,
        "point_diff_pg": 13.0,
        "recent_form": "WL",
        "completed_games": [
            {"location": "home", "result": "W", "points_for": 42, "points_against": 7},
            {"location": "away", "result": "L", "points_for": 26, "points_against": 35},
        ],
    }
    away = step2.build_team_profile_contract(
        away_evidence,
        {"team": "Coastal Carolina"},
        side="away",
    )
    home = step2.build_team_profile_contract(
        home_evidence,
        {"team": "Delaware"},
        side="home",
    )
    assert away["sample_games"] == 2
    assert away["recent_form"] == "LW"
    assert away["split_summary"] == "Away 0-1"
    assert home["sample_games"] == 2
    assert home["recent_form"] == "WL"
    assert home["split_summary"] == "Home 1-0"
