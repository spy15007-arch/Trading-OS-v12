import tempfile
import unittest
from pathlib import Path

import pandas as pd

from scanner.core.outcome_tracker import update_trade_outcomes


def history(rows):
    index = pd.to_datetime([row[0] for row in rows])
    return pd.DataFrame(
        {
            "Open": [row[1] for row in rows],
            "High": [row[2] for row in rows],
            "Low": [row[3] for row in rows],
            "Close": [row[4] for row in rows],
            "Volume": [1000] * len(rows),
        },
        index=index,
    )


def signal():
    return {
        "symbol": "TEST",
        "setup": "PRE-BREAKOUT",
        "score": 88,
        "entry": 100,
        "stop_loss": 95,
        "target_1": 105,
        "target_2": 110,
        "target_3": 115,
        "target_4": 120,
    }


class OutcomeTrackerTests(unittest.TestCase):
    def test_tracks_targets_then_stop_without_duplicate_active_signal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "trade_outcomes.csv"
            first = history([("2026-10-01", 99, 101, 98, 100)])
            update_trade_outcomes([signal()], {"TEST": first}, path)

            second = history([
                ("2026-10-01", 99, 101, 98, 100),
                ("2026-10-02", 101, 111, 100, 110),
            ])
            update_trade_outcomes([signal()], {"TEST": second}, path)
            frame = pd.read_csv(path).fillna("")
            self.assertEqual(len(frame), 1)
            self.assertEqual(frame.iloc[0]["t1_hit_date"], "2026-10-02")
            self.assertEqual(frame.iloc[0]["t2_hit_date"], "2026-10-02")
            self.assertEqual(frame.iloc[0]["status"], "ACTIVE")

            third = history([
                ("2026-10-01", 99, 101, 98, 100),
                ("2026-10-02", 101, 111, 100, 110),
                ("2026-10-05", 100, 108, 94, 96),
            ])
            update_trade_outcomes([], {"TEST": third}, path)
            frame = pd.read_csv(path).fillna("")
            self.assertEqual(len(frame), 1)
            self.assertEqual(frame.iloc[0]["status"], "STOP_AFTER_TARGET")
            self.assertEqual(frame.iloc[0]["stop_hit_date"], "2026-10-05")
            self.assertEqual(frame.iloc[0]["sessions_tracked"], 2)

    def test_same_daily_bar_stop_and_target_is_conservative(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "trade_outcomes.csv"
            first = history([("2026-10-01", 99, 101, 98, 100)])
            update_trade_outcomes([signal()], {"TEST": first}, path)
            second = history([
                ("2026-10-01", 99, 101, 98, 100),
                ("2026-10-02", 100, 106, 94, 99),
            ])
            update_trade_outcomes([], {"TEST": second}, path)
            frame = pd.read_csv(path).fillna("")
            self.assertEqual(frame.iloc[0]["status"], "STOP_LOSS")
            self.assertEqual(frame.iloc[0]["first_event"], "STOP_FIRST_AMBIGUOUS_BAR")
            self.assertEqual(frame.iloc[0]["t1_hit_date"], "")


if __name__ == "__main__":
    unittest.main()
