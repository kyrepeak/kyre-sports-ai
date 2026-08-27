import unittest
from unittest.mock import patch

from sports_api.collectors.wnba_kyre_market_feed import (
    DEFAULT_KYRE_MARKET_FEED_PATH,
    KYRE_MARKET_FEED_PATH_ENV,
    MARKET_PROVIDER_MODE_ENV,
)
from sports_api.tools import wnba_step6j_render_canary_contract as c
from sports_api.wnba_render_attachment_readiness import (
    DEFAULT_DISK_MOUNT_PATH,
    DEFAULT_DISK_NAME,
    DEFAULT_DISK_SIZE_GB,
)
from sports_api.wnba_render_provisioning_step6c import INGEST_TOKEN_ENV


class FakeClient:
    def __init__(self, services, disks, envs):
        self.services = services
        self.disks = disks
        self.envs = envs

    def request(self, method, path, *, params=None, json_body=None, allowed=(200,)):
        assert method == "GET"
        assert path == "/v1/services"
        return [{"service": row} for row in self.services]

    def list_disks(self, service_id):
        return self.disks.get(service_id, [])

    def list_env_vars(self, service_id):
        environment = self.envs.get(service_id, {})
        return [{"key": key, "value": value} for key, value in environment.items()]


def frozen_env():
    return {
        MARKET_PROVIDER_MODE_ENV: "kyre",
        KYRE_MARKET_FEED_PATH_ENV: DEFAULT_KYRE_MARKET_FEED_PATH,
        "WNBA_PROP_FEED_FAILOVER_ORDER": "kyre",
        "WNBA_PERSISTENT_VOLUME_ROOT": DEFAULT_DISK_MOUNT_PATH,
        "WNBA_STAGING_HOST_PROVIDER": "render",
        "WNBA_HOST_ENVIRONMENT": "staging",
        INGEST_TOKEN_ENV: "secret-never-returned",
        "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
    }


def frozen_disk():
    return {
        "id": "dsk-aaaaaaaaaaaaaaaaaaaa",
        "name": DEFAULT_DISK_NAME,
        "mountPath": DEFAULT_DISK_MOUNT_PATH,
        "sizeGB": DEFAULT_DISK_SIZE_GB,
    }


def service(service_id, name):
    return {
        "id": service_id,
        "name": name,
        "image": {"imagePath": "ghcr.io/kyrepeak/kyre-sports-api@sha256:" + "1" * 64},
        "serviceDetails": {"url": "https://example.onrender.com"},
    }


class Step6JRenderContractDiscoveryTests(unittest.TestCase):
    def test_01_display_name_is_not_part_of_identity(self):
        sid = "srv-aaaaaaaaaaaaaaaaaaaa"
        client = FakeClient(
            [service(sid, "totally-different-display-name")],
            {sid: [frozen_disk()]},
            {sid: frozen_env()},
        )
        matches = c.discover_frozen_step6c_services(client, "tea-test")
        self.assertEqual(1, len(matches))
        self.assertEqual(sid, matches[0]["id"])

    def test_02_wrong_disk_is_rejected(self):
        sid = "srv-aaaaaaaaaaaaaaaaaaaa"
        bad_disk = frozen_disk()
        bad_disk["mountPath"] = "/tmp/not-the-durable-volume"
        client = FakeClient([service(sid, "anything")], {sid: [bad_disk]}, {sid: frozen_env()})
        self.assertEqual([], c.discover_frozen_step6c_services(client, "tea-test"))

    def test_03_wrong_market_provider_is_rejected(self):
        sid = "srv-aaaaaaaaaaaaaaaaaaaa"
        env = frozen_env()
        env[MARKET_PROVIDER_MODE_ENV] = "legacy_sportsgameodds"
        client = FakeClient([service(sid, "anything")], {sid: [frozen_disk()]}, {sid: env})
        self.assertEqual([], c.discover_frozen_step6c_services(client, "tea-test"))

    def test_04_missing_ingest_token_is_rejected(self):
        sid = "srv-aaaaaaaaaaaaaaaaaaaa"
        env = frozen_env()
        env.pop(INGEST_TOKEN_ENV)
        client = FakeClient([service(sid, "anything")], {sid: [frozen_disk()]}, {sid: env})
        self.assertEqual([], c.discover_frozen_step6c_services(client, "tea-test"))

    def test_05_wrapper_restores_original_client_method(self):
        original = c.RenderAPIClient.list_services
        expected = {"completed": True, "safety": {}}
        with patch.object(c.base, "run_render_canary", return_value=expected.copy()) as run:
            result = c.run_render_canary_with_contract_discovery(
                revision="a" * 40,
                release_id="release",
                image_ref="ghcr.io/kyrepeak/kyre-sports-api@sha256:" + "b" * 64,
                activation_id="step6j-test-002",
                date="2026-08-27",
                season=2026,
                api_key="test-key",
                owner_id=None,
            )
        self.assertIs(c.RenderAPIClient.list_services, original)
        self.assertEqual("frozen_step6c_contract", result["service_discovery"]["strategy"])
        run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
