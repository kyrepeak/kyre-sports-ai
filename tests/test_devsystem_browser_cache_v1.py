from pathlib import Path


WORKFLOW = Path('.github/workflows/devsystem-targeted-ci.yml')
EPOCH = Path('devsystem/browser_cache_epoch_v1.txt')
TOOLING = Path('devsystem/browser_tooling_v1.txt')
BROWSER_QA = Path('devsystem/browser_qa_v1.py')
PRODUCTION_V5 = Path('.github/workflows/devsystem-production-verification-v5.yml')


def _browser_lane(text: str) -> str:
    return text.split('  browser-qa:', 1)[1].split('  cfb-critical:', 1)[0]


def test_browser_cache_contract_is_present_and_fail_safe():
    text = WORKFLOW.read_text(encoding='utf-8')
    lane = _browser_lane(text)
    browser_qa = BROWSER_QA.read_text(encoding='utf-8')

    assert 'Restore Browser QA stack' in lane
    assert 'id: browser-stack-cache' in lane
    assert lane.count('uses: actions/cache@v4') == 1
    assert '.venv-browser-qa' in lane
    assert '~/.cache/ms-playwright' in lane
    assert "steps.browser-stack-cache.outputs.cache-hit != 'true'" in lane
    assert 'Build Browser QA stack on cache miss' in lane
    assert '-r devsystem/browser_tooling_v1.txt' in lane
    assert 'python -m playwright install chromium' in lane
    assert 'Resolve Playwright cache identity' not in lane
    assert 'Restore Playwright browser binaries' not in lane
    assert 'Verify Chromium can launch' not in lane
    assert 'sync_playwright()' in browser_qa
    assert 'p.chromium.launch(' in browser_qa
    assert 'DEVSYSTEM_BROWSER_QA_GREEN' in browser_qa


def test_browser_stack_cache_is_bound_to_python_requirements_and_tooling():
    text = WORKFLOW.read_text(encoding='utf-8')
    lane = _browser_lane(text)

    assert 'id: browser-python' in lane
    assert 'steps.browser-python.outputs.python-version' in lane
    assert "devsystem-browser-stack-${{ runner.os }}-py${{ steps.browser-python.outputs.python-version }}-${{ hashFiles('requirements.txt', 'devsystem/browser_tooling_v1.txt', 'devsystem/browser_cache_epoch_v1.txt') }}" in lane


def test_browser_tooling_pins_playwright_identity():
    text = TOOLING.read_text(encoding='utf-8')

    assert 'pytest' in text
    assert 'requests' in text
    assert 'playwright==1.62.0' in text


def test_browser_cache_contract_tests_run_inside_protected_browser_lane():
    text = WORKFLOW.read_text(encoding='utf-8')
    lane = _browser_lane(text)

    assert 'Self-test browser QA and cache contracts' in lane
    assert 'tests/test_devsystem_browser_qa_v1.py' in lane
    assert 'tests/test_devsystem_browser_cache_v1.py' in lane


def test_browser_cache_keeps_real_qa_and_avoids_duplicate_restore_actions():
    text = WORKFLOW.read_text(encoding='utf-8')
    lane = _browser_lane(text)

    assert 'playwright install --with-deps chromium' not in lane
    assert 'Restore browser QA virtualenv' not in lane
    assert 'Restore Playwright browser binaries' not in lane
    assert 'python devsystem/browser_qa_v1.py' in lane
    assert '--base-url http://127.0.0.1:8501' in lane
    assert 'Upload browser QA evidence' in lane


def test_browser_cache_epoch_is_explicit_and_versioned():
    text = EPOCH.read_text(encoding='utf-8')

    assert 'DEVSYSTEM_BROWSER_CACHE_EPOCH=1' in text
    assert 'Bump the epoch' in text


def test_production_v5_reuses_seeded_browser_stack_instead_of_reinstalling():
    text = PRODUCTION_V5.read_text(encoding='utf-8')

    assert 'Restore shared Browser QA stack' in text
    assert 'id: browser-stack-cache' in text
    assert '.venv-browser-qa' in text
    assert '~/.cache/ms-playwright' in text
    assert "steps.browser-stack-cache.outputs.cache-hit != 'true'" in text
    assert 'Build shared Browser QA stack on cache miss' in text
    assert '-r devsystem/browser_tooling_v1.txt' in text
    assert 'python -m playwright install chromium' in text
    assert 'Activate shared Browser QA virtualenv' in text
    assert 'playwright install --with-deps chromium' not in text
    assert 'Install production verification dependencies' not in text


def test_production_v5_cache_key_matches_seeded_browser_qa_cache():
    text = PRODUCTION_V5.read_text(encoding='utf-8')
    expected = "devsystem-browser-stack-${{ runner.os }}-py${{ steps.browser-python.outputs.python-version }}-${{ hashFiles('requirements.txt', 'devsystem/browser_tooling_v1.txt', 'devsystem/browser_cache_epoch_v1.txt') }}"
    assert expected in text


def test_production_v5_runs_cheap_preflight_before_browser_restore():
    text = PRODUCTION_V5.read_text(encoding='utf-8')

    preflight = '\n      - name: Run dependency-free production preflight'
    restore = '\n      - name: Restore shared Browser QA stack'
    assert preflight in text
    assert restore in text
    assert text.index(preflight) < text.index(restore)

    lane = text[text.index(preflight):text.index(restore)]
    assert 'python -m py_compile' in lane
    assert 'devsystem/production_verify_v5.py' in lane
    assert 'devsystem/production_identity_verify_v1.py' in lane
    assert 'DEVSYSTEM_PRODUCTION_V5_CHEAP_PREFLIGHT_GREEN' in lane
    assert 'pip install' not in lane
    assert 'playwright install' not in lane


def test_production_v5_step3_preserves_step2_cache_contract():
    text = PRODUCTION_V5.read_text(encoding='utf-8')

    assert 'Run dependency-free production preflight' in text
    assert 'Restore shared Browser QA stack' in text
    assert "steps.browser-stack-cache.outputs.cache-hit != 'true'" in text
    assert '.venv-browser-qa' in text
    assert '~/.cache/ms-playwright' in text
    assert 'playwright install --with-deps chromium' not in text


def test_production_v5_push_scope_is_narrow_and_cfb_owned():
    text = PRODUCTION_V5.read_text(encoding='utf-8')
    push_block = text.split('  push:', 1)[1].split('  workflow_dispatch:', 1)[0]

    # Step 4 removes repo-wide fanout that made unrelated NFL/WNBA/MLB work
    # launch the expensive public CFB production verifier.
    assert '- "streamlit_*.py"' not in push_block
    assert '- "sports_api/**"' not in push_block
    assert '- "data/**"' not in push_block

    # Keep the real V5 production ownership surface automatic.
    required = (
        '- "app.py"',
        '- "streamlit_memory_lazy_router_v240.py"',
        '- "kyre_universal_shell_runtime_v1.py"',
        '- "cfb_*.py"',
        '- "sports_api/api/cfb*.py"',
        '- "sports_api/collectors/cfb_*.py"',
        '- "data/cfb_*.json"',
        '- "requirements*.txt"',
        '- "devsystem/production_verify_v5.py"',
        '- ".github/workflows/devsystem-production-verification-v5.yml"',
    )
    for token in required:
        assert token in push_block


def test_production_v5_step4_preserves_steps_2_and_3_speed_contracts():
    text = PRODUCTION_V5.read_text(encoding='utf-8')

    assert 'Run dependency-free production preflight' in text
    assert text.index('Run dependency-free production preflight') < text.index('Restore shared Browser QA stack')
    assert "steps.browser-stack-cache.outputs.cache-hit != 'true'" in text
    assert '.venv-browser-qa' in text
    assert '~/.cache/ms-playwright' in text
    assert 'playwright install --with-deps chromium' not in text
