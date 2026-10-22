from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERCEL_API = ROOT / "kyre_sports_api_vercel_v1.py"
GATEWAY = ROOT / "nfl_passing_yards_gateway_v1.py"


def test_vercel_api_registers_nfl_passing_yards_page_router() -> None:
    source = VERCEL_API.read_text(encoding="utf-8")
    assert "sports_api.api.nfl_passing_yards_page_v1" in source
    assert "app.include_router(nfl_passing_yards_page_router)" in source
    assert '"nfl_passing_yards_page": True' in source


def test_streamlit_gateway_defaults_to_vercel_kyre_sports_api() -> None:
    source = GATEWAY.read_text(encoding="utf-8")
    assert 'DEFAULT_API_BASE_URL = "https://kyre-sports-api.vercel.app"' in source
    assert "kyre-sports-api.onrender.com" not in source
