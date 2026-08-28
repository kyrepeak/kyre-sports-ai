from sports_api import wnba_step17a_production_host_contract as s17a


def _env():
    env = s17a.expected_host_env()
    env["KYRE_DATABASE_URL"] = "postgresql://user:secret@example.invalid/kyre"
    return env


def _service():
    return {
        "id": s17a.EXPECTED_RENDER_SERVICE_ID,
        "name": s17a.EXPECTED_RENDER_SERVICE_NAME,
        "type": s17a.EXPECTED_RENDER_SERVICE_TYPE,
        "repo": s17a.EXPECTED_RENDER_REPOSITORY,
        "serviceDetails": {
            "runtime": s17a.EXPECTED_RENDER_RUNTIME,
            "url": s17a.EXPECTED_RENDER_URL,
        },
    }


def test_step17a_accepts_exact_frozen_release_with_scheduler_off():
    report = s17a.validate_host_contract(_env(), build_revision=s17a.STEP16E_FROZEN_SHA)
    assert report["status"] == "host_contract_ready_scheduler_off"
    assert report["scheduler_enabled"] is False
    assert report["new_render_service_creation_allowed"] is False
    assert report["database_secret_exposed"] is False
    assert report["render_service_id"] == s17a.EXPECTED_RENDER_SERVICE_ID


def test_step17a_accepts_exact_existing_render_identity():
    observed = s17a.validate_render_service_identity(_service())
    assert observed["id"] == s17a.EXPECTED_RENDER_SERVICE_ID
    assert observed["runtime"] == "docker"


def test_step17a_refuses_render_identity_drift():
    service = _service()
    service["id"] = "srv-aaaaaaaaaaaaaaaaaaaa"
    try:
        s17a.validate_render_service_identity(service)
    except s17a.Step17AHostContractError:
        return
    raise AssertionError("Render service identity drift must fail closed")


def test_step17a_refuses_scheduler_activation():
    env = _env()
    env["WNBA_BOARD_SCHEDULER_ENABLED"] = "true"
    try:
        s17a.validate_host_contract(env)
    except s17a.Step17AHostContractError:
        return
    raise AssertionError("Step 17A must fail closed when scheduler is enabled")


def test_step17a_refuses_wrong_revision_or_missing_db_secret():
    env = _env()
    env[s17a.EXPECTED_REVISION_ENV] = "0" * 40
    try:
        s17a.validate_host_contract(env)
    except s17a.Step17AHostContractError:
        pass
    else:
        raise AssertionError("wrong revision must fail")
    env = s17a.expected_host_env()
    try:
        s17a.validate_host_contract(env)
    except s17a.Step17AHostContractError:
        return
    raise AssertionError("missing DB secret must fail")


if __name__ == "__main__":
    test_step17a_accepts_exact_frozen_release_with_scheduler_off()
    test_step17a_accepts_exact_existing_render_identity()
    test_step17a_refuses_render_identity_drift()
    test_step17a_refuses_scheduler_activation()
    test_step17a_refuses_wrong_revision_or_missing_db_secret()
    print("STEP17A_HOST_CONTRACT_TESTS_OK")
