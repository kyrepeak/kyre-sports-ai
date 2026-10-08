from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
SUBJECT = ROOT / "cfb_game_total_page1_v2_step4_side_market_completeness_v1.py"
THEME = ROOT / "kyre_remaining_pages_theme_v1.py"
PREDICTION = ROOT / "cfb_game_total_page1_step4_prediction_market_v1.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _payload(provider_game_id: str = "fd-abc"):
    def odds(value: int):
        return {"americanDisplayOdds": {"americanOddsInt": value}}

    return {
        "attachments": {
            "markets": {
                "ml": {
                    "eventId": provider_game_id,
                    "marketName": "Moneyline",
                    "marketType": "MONEY_LINE",
                    "marketStatus": "OPEN",
                    "inPlay": False,
                    "runners": [
                        {"side": "AWAY", "runnerStatus": "ACTIVE", "winRunnerOdds": odds(155)},
                        {"side": "HOME", "runnerStatus": "ACTIVE", "winRunnerOdds": odds(-188)},
                    ],
                },
                "spread": {
                    "eventId": provider_game_id,
                    "marketName": "Spread",
                    "marketType": "SPREAD",
                    "marketStatus": "OPEN",
                    "inPlay": False,
                    "runners": [
                        {"side": "AWAY", "runnerStatus": "ACTIVE", "handicap": 3.5, "winRunnerOdds": odds(-105)},
                        {"side": "HOME", "runnerStatus": "ACTIVE", "handicap": -3.5, "winRunnerOdds": odds(-115)},
                    ],
                },
            }
        }
    }


def _display_game():
    return {
        "event_id": "401000001",
        "game_date": "2026-10-09",
        "away_team": "Florida State",
        "home_team": "Louisville",
        "market_identity_verified": True,
        "market_official_game_id": "401000001",
        "market_provider_game_id": "fd-abc",
        "market_sportsbook": "FanDuel",
        "market_total": 59.5,
        "market_projection_weight": 0.0,
    }


def test_side_market_completeness_subject_exists_before_green() -> None:
    assert SUBJECT.exists(), "FanDuel exact-provider side-market completeness helper is required"


def test_exact_verified_fanduel_provider_id_populates_spread_and_moneyline() -> None:
    subject = _load(SUBJECT, "step4_side_market_completeness")
    enriched = subject.enrich_verified_side_market(
        _display_game(), payload_loader=lambda: _payload()
    )
    assert enriched["verified_away_spread"] == 3.5
    assert enriched["verified_home_spread"] == -3.5
    assert enriched["verified_away_moneyline"] == 155
    assert enriched["verified_home_moneyline"] == -188
    assert enriched["verified_side_market_provider"] == "FanDuel"
    assert enriched["verified_side_market_event_id"] == "401000001"
    assert enriched["verified_side_market_provider_event_id"] == "fd-abc"
    assert enriched["verified_side_market_projection_weight"] == 0.0
    assert enriched["verified_side_market_status"] == "GREEN"
    assert enriched["verified_side_market_identity_method"] == "Kyre verified official event -> exact FanDuel provider_game_id"


def test_provider_event_mismatch_fails_closed_and_can_fall_back() -> None:
    subject = _load(SUBJECT, "step4_side_market_completeness_miss")

    def legacy(game):
        out = dict(game)
        out.update(
            {
                "verified_away_spread": 4.5,
                "verified_home_spread": -4.5,
                "verified_away_moneyline": 160,
                "verified_home_moneyline": -190,
                "verified_side_market_provider": "Legacy Exact Event",
                "verified_side_market_status": "GREEN",
                "verified_side_market_projection_weight": 0.0,
            }
        )
        return out

    enriched = subject.enrich_verified_side_market(
        _display_game(),
        payload_loader=lambda: _payload("different-provider-event"),
        legacy_enricher=legacy,
    )
    assert enriched["verified_side_market_provider"] == "Legacy Exact Event"
    assert enriched["verified_away_spread"] == 4.5
    assert enriched["verified_away_moneyline"] == 160


def test_direct_fanduel_path_rejects_ambiguous_or_nonzero_projection_semantics() -> None:
    subject = _load(SUBJECT, "step4_side_market_completeness_guard")
    game = _display_game()
    game["market_projection_weight"] = 1.0
    called = {"legacy": 0}

    def legacy(value):
        called["legacy"] += 1
        out = dict(value)
        out["verified_side_market_status"] = "UNAVAILABLE"
        return out

    enriched = subject.enrich_verified_side_market(
        game, payload_loader=lambda: _payload(), legacy_enricher=legacy
    )
    assert called["legacy"] == 1
    assert enriched["verified_side_market_status"] == "UNAVAILABLE"
    assert "verified_away_moneyline" not in enriched


def test_prediction_card_renders_verified_fanduel_spread_and_moneyline() -> None:
    subject = _load(SUBJECT, "step4_side_market_completeness_render")
    prediction = _load(PREDICTION, "step4_prediction_renderer_side_market_complete")
    game = subject.enrich_verified_side_market(
        _display_game(), payload_loader=lambda: _payload()
    )
    html = prediction.build_prediction_market_html(
        {"projected_combined_total": 73.7},
        {"ready": True, "projected_combined_total": 73.7, "forecast_strength": 0.792, "grade": "B"},
        game,
        {},
        10,
    )
    assert "Florida State +3.5" in html
    assert "Louisville -3.5" in html
    assert "Florida State +155" in html
    assert "Louisville -188" in html
    assert "Side market FanDuel • exact event ID" in html
    assert "0.0% sportsbook projection influence" in html


def test_unfrozen_theme_gate_installs_only_for_cfb_game_total() -> None:
    text = THEME.read_text(encoding="utf-8")
    assert "install_side_market_completeness" in text
    assert '(sport, market) == ("CFB", "Game Total")' in text
    assert "cfb_game_total_page1_v2_step4_side_market_completeness_v1" in text
