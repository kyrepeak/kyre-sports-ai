import os
import unittest
from unittest.mock import patch


class MonsterTelemetryProbeV1Tests(unittest.TestCase):
    def test_probe_is_disabled_by_default(self):
        from sports_api.monster_telemetry_probe_v1 import telemetry_probe_enabled

        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(telemetry_probe_enabled())

    def test_enabled_probe_queues_synthetic_exception_with_certification_marker(self):
        from sports_api import monster_telemetry_probe_v1 as probe

        with patch.dict(os.environ, {"MONSTER_TELEMETRY_PROBE_ENABLED": "1"}, clear=False):
            with patch.object(probe, "capture_runtime_exception", return_value=True) as capture:
                result = probe.run_telemetry_probe()

        self.assertEqual(result["status"], "queued")
        self.assertTrue(result["accepted"])
        self.assertTrue(result["marker"].startswith("monster-a6-"))
        self.assertEqual(result["probe_version"], "MONSTER_TELEMETRY_PROBE_V1")
        capture.assert_called_once()
        kwargs = capture.call_args.kwargs
        self.assertEqual(kwargs["error_fingerprint"], "MONSTER-A6-PROBE-V1")
        self.assertEqual(kwargs["surface"], "sports_api")
        self.assertEqual(kwargs["path"], "/health/telemetry/probe")
        self.assertTrue(kwargs["properties"]["monster_certification_probe"].startswith("monster-a6-"))
        self.assertTrue(kwargs["properties"]["synthetic_certification_probe"])


if __name__ == "__main__":
    unittest.main()
