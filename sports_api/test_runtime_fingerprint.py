from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from sports_api.runtime_fingerprint import fingerprint_source_files


class RuntimeFingerprintTests(TestCase):
    def test_fingerprint_is_deterministic_and_changes_with_source_bytes(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first.py"
            second = root / "second.py"
            first.write_bytes(b"VALUE = 1\n")
            second.write_bytes(b"VALUE = 2\n")

            fingerprint_a = fingerprint_source_files(
                {
                    "sports_api/second.py": second,
                    "sports_api/first.py": first,
                }
            )
            fingerprint_b = fingerprint_source_files(
                {
                    "sports_api/first.py": first,
                    "sports_api/second.py": second,
                }
            )

            self.assertEqual(
                fingerprint_a["runtime_source_sha256"],
                fingerprint_b["runtime_source_sha256"],
            )
            self.assertEqual(
                [entry["path"] for entry in fingerprint_a["files"]],
                ["sports_api/first.py", "sports_api/second.py"],
            )

            first.write_bytes(b"VALUE = 3\n")
            fingerprint_changed = fingerprint_source_files(
                {
                    "sports_api/first.py": first,
                    "sports_api/second.py": second,
                }
            )

            self.assertNotEqual(
                fingerprint_a["runtime_source_sha256"],
                fingerprint_changed["runtime_source_sha256"],
            )
