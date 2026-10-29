import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from early_momentum_radar import evaluate_stock, _radar_report_already_sent, _save_radar_report_signature


def make_history(kind="watch", n=250):
    idx = pd.bdate_range("2025-01-01", periods=n)
    close = np.linspace(80, 110, n)
    open_ = close * 0.997
    high = close * 1.008
    low = close * 0.992
    volume = np.full(n, 100_000.0)

    if kind == "watch":
        close[-22:-1] = np.linspace(108.0, 111.0, 21)
        high[-22:-1] = close[-22:-1] * 1.006
        low[-22:-1] = close[-22:-1] * 0.994
        close[-1], open_[-1], high[-1], low[-1], volume[-1] = 110.0, 109.5, 110.6, 109.2, 100_000
    elif kind == "breakout":
        close[-22:-1] = np.linspace(108.0, 109.5, 21) + 0.6 * np.sin(np.arange(21) * 1.7)
        high[-22:-1] = close[-22:-1] * 1.004
        low[-22:-1] = close[-22:-1] * 0.996
        close[-1], open_[-1], high[-1], low[-1], volume[-1] = 111.0, 109.8, 111.2, 109.5, 150_000
    elif kind == "chase":
        close[-1], open_[-1], high[-1], low[-1], volume[-1] = 125.0, 123.0, 125.5, 122.5, 200_000

    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume}, index=idx)


class EarlyMomentumRadarTests(unittest.TestCase):
    def test_unchanged_radar_report_is_suppressed_across_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "radar_state.json"
            first = "EARLY RADAR\nScan: EARLY_WATCH | Snapshot: 18:00\nCandidate: ABC | Price 100"
            second = "EARLY RADAR\nScan: PRE_CLOSE_CHECK | Snapshot: 20:00\nCandidate: ABC | Price 100"
            self.assertFalse(_radar_report_already_sent(first, state))
            _save_radar_report_signature(first, state)
            self.assertTrue(_radar_report_already_sent(second, state))

    def test_changed_radar_candidate_is_not_suppressed(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "radar_state.json"
            first = "EARLY RADAR\nScan: EARLY_WATCH | Snapshot: 18:00\nCandidate: ABC | Price 100"
            changed = "EARLY RADAR\nScan: PRE_CLOSE_CHECK | Snapshot: 20:00\nCandidate: ABC | Price 103"
            _save_radar_report_signature(first, state)
            self.assertFalse(_radar_report_already_sent(changed, state))

    def test_early_watch_near_resistance_is_detected(self):
        candidate, reason = evaluate_stock("TEST.NS", make_history("watch"))
        self.assertIsNone(reason)
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["setup"], "EARLY WATCH")

    def test_first_breakout_candle_is_detected(self):
        candidate, reason = evaluate_stock("TEST.NS", make_history("breakout"))
        self.assertIsNone(reason)
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["setup"], "FIRST-CANDLE BREAKOUT")

    def test_overextended_stock_is_not_chased(self):
        candidate, reason = evaluate_stock("TEST.NS", make_history("chase"))
        self.assertIsNone(candidate)
        self.assertIn(reason, {"TOO_EXTENDED_FROM_EMA20", "ALREADY_EXTENDED_ABOVE_RESISTANCE"})


if __name__ == "__main__":
    unittest.main()
