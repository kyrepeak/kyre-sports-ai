from pathlib import Path


MODULE_PATH = Path("nba_spread_sharp_money_observations_v1.py")


def test_step3_sharp_money_observation_adapter_exists():
    assert MODULE_PATH.exists(), "Step 3 sharp-money observation adapter does not exist yet"
