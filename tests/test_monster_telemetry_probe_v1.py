import os
import unittest
from unittest.mock import Mock, patch


class MonsterTelemetryProbeV1Tests(unittest.TestCase):
    def test_probe_is_disabled_by_default(self):
        from sports_api.monster_telemetry_probe_v1 import telemetry_probe_enabled

        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(telemetry_probe_enabled())

    def test_enabled_probe_without_posthog_client_reports_not_flushed(self):
        from sports_api import monster_telemetry_probe_v1 as probe

        with patch.dict(os.environ, {"MONSTER_TELEMETRY_PROBE_ENABLED": "1"}, clear=False):
            with patch.object(probe, "get_posthog_client", return_value=None):
                with patch.object(probe, "capture_runtime_exception", return_value=True) as capture:
                    with patch.object(
                        probe,
                        "radar_status",
                        return_value={"configured": False, "host": "https://us.i.posthog.com"},
                    ):
                        result = probe.run_telemetry_probe()

        self.assertEqual(result["status"], "not_flushed")
        self.assertTrue(result["accepted"])
        self.assertFalse(result["transport_queued"])
        self.assertFalse(result["flushed"])
        self.assertTrue(result["marker"].startswith("monster-a6-"))
        self.assertEqual(result["probe_version"], "MONSTER_TELEMETRY_PROBE_V1")
        capture.assert_called_once()
        kwargs = capture.call_args.kwargs
        self.assertEqual(kwargs["error_fingerprint"], "MONSTER-A6-PROBE-V1")
        self.assertEqual(kwargs["surface"], "sports_api")
        self.assertEqual(kwargs["path"], "/health/telemetry/probe")
        self.assertTrue(kwargs["properties"]["monster_certification_probe"].startswith("monster-a6-"))
        self.assertTrue(kwargs["properties"]["synthetic_certification_probe"])

    def test_enabled_probe_queues_transport_and_flushes_when_client_available(self):
        from sports_api import monster_telemetry_probe_v1 as probe

        client = Mock()
        with patch.dict(os.environ, {"MONSTER_TELEMETRY_PROBE_ENABLED": "1"}, clear=False):
            with patch.object(probe, "get_posthog_client", return_value=client):
                with patch.object(probe, "capture_runtime_exception", return_value=True) as capture:
                    with patch.object(
                        probe,
                        "radar_status",
                        return_value={"configured": True, "host": "https://us.i.posthog.com"},
                    ):
                        result = probe.run_telemetry_probe()

        self.assertEqual(result["status"], "flushed")
        self.assertTrue(result["accepted"])
        self.assertTrue(result["transport_queued"])
        self.assertTrue(result["flushed"])
        self.assertIsNone(result["transport_error"])
        self.assertIsNone(result["flush_error"])
        self.assertTrue(result["marker"].startswith("monster-a6-"))
        self.assertEqual(result["probe_version"], "MONSTER_TELEMETRY_PROBE_V1")

        client.capture.assert_called_once()
        capture_args, capture_kwargs = client.capture.call_args
        self.assertEqual(capture_args[0], "monster_a6_transport_probe")
        self.assertEqual(capture_kwargs["distinct_id"], "monster-a6-certification")
        self.assertTrue(capture_kwargs["properties"]["monster_certification_probe"].startswith("monster-a6-"))
        self.assertTrue(capture_kwargs["properties"]["synthetic_certification_probe"])
        client.flush.assert_called_once_with()
        capture.assert_called_once()


if __name__ == "__main__":
    unittest.main()
