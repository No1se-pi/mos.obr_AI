import tempfile
import unittest
from pathlib import Path

from app.ingest.source_fingerprint import compute_data_fingerprint


class SourceFingerprintTest(unittest.TestCase):
    def test_fingerprint_changes_when_source_file_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "colleges.json"
            source.write_text('{"value": 1}', encoding="utf-8")

            first = compute_data_fingerprint([("colleges", source)])
            source.write_text('{"value": 2}', encoding="utf-8")
            second = compute_data_fingerprint([("colleges", source)])

        self.assertNotEqual(first, second)

    def test_fingerprint_is_stable_for_same_missing_sources(self) -> None:
        missing = Path("missing-data-file.json")

        first = compute_data_fingerprint([("colleges", missing)])
        second = compute_data_fingerprint([("colleges", missing)])

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
