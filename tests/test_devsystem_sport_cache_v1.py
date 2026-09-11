from pathlib import Path


WORKFLOW = Path('.github/workflows/devsystem-targeted-ci.yml')
SEED_WORKFLOW = Path('.github/workflows/devsystem-cache-seed-v1.yml')
EPOCH = Path('devsystem/sport_cache_epoch_v1.txt')


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def _seed_text() -> str:
    return SEED_WORKFLOW.read_text(encoding='utf-8')


def test_each_sport_critical_lane_has_isolated_exact_python_cache():
    text = _workflow_text()

    for sport in ('cfb', 'mlb', 'wnba'):
        upper = sport.upper()
        assert f'Set up {upper} Python' in text
        assert f'id: {sport}-python' in text
        assert f'Restore {upper} critical virtualenv' in text
        assert f'id: {sport}-venv-cache' in text
        assert f'.venv-{sport}-critical' in text
        assert f'steps.{sport}-python.outputs.python-version' in text
        assert f"steps.{sport}-venv-cache.outputs.cache-hit != 'true'" in text
        assert f'Activate {upper} critical virtualenv' in text


def test_cache_keys_follow_each_lane_requirement_surface():
    text = _workflow_text()

    assert "devsystem-cfb-venv-${{ runner.os }}-py${{ steps.cfb-python.outputs.python-version }}-${{ hashFiles('requirements.txt', 'devsystem/sport_cache_epoch_v1.txt') }}" in text
    assert "devsystem-mlb-venv-${{ runner.os }}-py${{ steps.mlb-python.outputs.python-version }}-${{ hashFiles('requirements.txt', 'sports_api/requirements.txt', 'devsystem/sport_cache_epoch_v1.txt') }}" in text
    assert "devsystem-wnba-venv-${{ runner.os }}-py${{ steps.wnba-python.outputs.python-version }}-${{ hashFiles('sports_api/requirements.txt', 'devsystem/sport_cache_epoch_v1.txt') }}" in text


def test_cache_misses_rebuild_and_frozen_test_commands_remain_present():
    text = _workflow_text()

    assert '.venv-cfb-critical/bin/python -m pip install --disable-pip-version-check -q -r requirements.txt' in text
    assert '.venv-mlb-critical/bin/python -m pip install --disable-pip-version-check -q -r requirements.txt' in text
    assert '.venv-mlb-critical/bin/python -m pip install --disable-pip-version-check -q -r sports_api/requirements.txt' in text
    assert '.venv-wnba-critical/bin/python -m pip install --disable-pip-version-check -q -r sports_api/requirements.txt' in text

    assert 'tests/test_cfb_over_under_upgrade_step12_certification.py' in text
    assert 'tests/test_mlb_step20b_production_release_certification_v1.py' in text
    assert 'tests/test_wnba_step20b_monte_carlo_acceleration.py' in text


def test_main_cache_seed_is_trusted_scoped_and_key_aligned():
    targeted = _workflow_text()
    seed = _seed_text()

    assert 'name: DevSystem cache seed' in seed
    assert 'branches: [main]' in seed
    assert 'workflow_dispatch:' in seed
    assert 'pull_request:' not in seed

    for marker in (
        'devsystem-browser-venv-',
        'devsystem-cfb-venv-',
        'devsystem-mlb-venv-',
        'devsystem-wnba-venv-',
    ):
        assert marker in targeted
        assert marker in seed

    assert 'devsystem-playwright-' not in targeted
    assert 'devsystem-playwright-' not in seed
    assert 'Restore Playwright browser binaries' not in targeted
    assert 'Restore Playwright browser binaries' not in seed
    assert 'python -m playwright install chromium' not in targeted
    assert 'python -m playwright install chromium' not in seed

    assert 'devsystem/sport_cache_epoch_v1.txt' in seed
    assert 'devsystem/browser_cache_epoch_v1.txt' in seed
    assert '.github/workflows/devsystem-cache-seed-v1.yml' in seed


def test_sport_cache_contract_is_permanently_exercised():
    text = _workflow_text()

    assert 'tests/test_devsystem_sport_cache_v1.py' in text
    assert 'Self-test classifier and final gate' in text


def test_sport_cache_epoch_is_explicit_and_versioned():
    text = EPOCH.read_text(encoding='utf-8')

    assert 'DEVSYSTEM_SPORT_CACHE_EPOCH=1' in text
    assert 'Bump the epoch' in text
