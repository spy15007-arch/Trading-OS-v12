import tempfile
import unittest
from pathlib import Path

from telegram_push import _is_duplicate_report, _save_report_signature


class TelegramReportDedupeTests(unittest.TestCase):
    def test_same_report_with_different_scan_mode_is_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "swing_scan.csv"
            first = "TRADING OS\nScan mode: MIDDAY_RADAR\nCandidate: ABC | Price 100"
            second = "TRADING OS\nScan mode: CLOSE_CONFIRMATION\nCandidate: ABC | Price 100"

            self.assertFalse(_is_duplicate_report(first, csv_path))
            _save_report_signature(first, csv_path)
            self.assertTrue(_is_duplicate_report(second, csv_path))

    def test_changed_candidate_details_are_not_suppressed(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "swing_scan.csv"
            first = "TRADING OS\nScan mode: MIDDAY_RADAR\nCandidate: ABC | Price 100"
            changed = "TRADING OS\nScan mode: CLOSE_CONFIRMATION\nCandidate: ABC | Price 103"

            _save_report_signature(first, csv_path)
            self.assertFalse(_is_duplicate_report(changed, csv_path))


if __name__ == "__main__":
    unittest.main()
