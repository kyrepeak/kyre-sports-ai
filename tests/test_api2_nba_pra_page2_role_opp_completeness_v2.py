from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_player_context_module():
    base = _load_module(
        ROOT / "sports_api" / "api" / "nba_pra_player_context_v1.py",
        "api2_prod_nba_pra_player_context_v1_test",
    )
    patch = _load_module(
        ROOT / "sports_api" / "api" / "nba_pra_player_context_completeness_v2.py",
        "api2_prod_nba_pra_player_context_completeness_v2_test",
    )
    patch.install(base)
    return base


def test_production_reference_game_log_preserves_opponent() -> None:
    ctx = _load_player_context_module()
    html = '''
    <table><tbody><tr>
      <td data-stat="date_game">2026-10-23</td>
      <td data-stat="opp_id">MIA</td>
      <td data-stat="mp">24:00</td>
      <td data-stat="pts">17</td>
      <td data-stat="trb">4</td>
      <td data-stat="ast">3</td>
    </tr></tbody></table>
    '''
    rows = ctx._parse_game_log(html)
    assert rows[0]["opponent"] == "MIA"


def test_production_cbs_game_log_preserves_opponent() -> None:
    ctx = _load_player_context_module()
    headers = ["date", "opponent", "result", "min", "pts", "reb", "ast"]
    values = ["Oct 23, 2026", "@ MIA", "W", "24", "17", "4", "3"]
    head = "".join(f"<th>{item}</th>" for item in headers)
    body = "".join(f"<td>{item}</td>" for item in values)
    html = f'<h4>2026-27 Regular Season Game Log</h4><table><thead><tr>{head}</tr></thead><tbody><tr>{body}</tr></tbody></table>'
    rows = ctx._parse_cbs_game_log_html(html)
    assert rows[0]["opponent"] == "MIA"


def test_production_gateway_activates_completeness_and_usage_successors() -> None:
    source = (ROOT / "kyre_sports_api_vercel_v1.py").read_text(encoding="utf-8")
    assert "sports_api.api.nba_pra_player_context_completeness_v2" in source
    assert "sports_api.api.nba_pra_player_context_enrichment_v2" in source
    assert "sports_api.api.nba_pra_usage_fallback_v2" in source
    assert "nba_pra_player_context_completeness_module.install(nba_pra_player_context_module)" in source
    assert (ROOT / "sports_api" / "api" / "nba_pra_usage_v1.py").exists()
    assert (ROOT / "sports_api" / "api" / "nba_pra_player_context_enrichment_v2.py").exists()
    assert (ROOT / "sports_api" / "api" / "nba_pra_usage_fallback_v2.py").exists()


def test_injury_dependency_is_static_and_bundle_visible() -> None:
    source = (ROOT / "sports_api" / "api" / "nba_pra_injury_v1.py").read_text(encoding="utf-8")
    function_pos = source.index("def collect_nba_pra_injuries")
    import_pos = source.index("from nba_spread_injury_availability_v1 import _fetch_official_rows")
    assert import_pos < function_pos


def test_model_and_frontend_ownership_remain_frozen() -> None:
    source = (ROOT / "nba_pra_page2_command_center_v3.py").read_text(encoding="utf-8")
    assert 'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0' in source
    assert "from nba_pra_page2_data_completeness_v1 import combined_verified_games" in source
