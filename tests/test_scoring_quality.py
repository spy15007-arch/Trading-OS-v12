import unittest

import pandas as pd

from scanner.core.scoring import _early_quality_metrics


class EarlyQualityMetricsTests(unittest.TestCase):
    def test_detects_tightening_ranges_and_volume_dryup(self):
        # First 20 sessions have wider daily ranges and heavier volume;
        # the last 5 sessions contract and show quieter volume.
        highs = [105.0] * 20 + [101.0] * 5
        lows = [95.0] * 20 + [99.0] * 5
        closes = [100.0] * 25
        volumes = [1000.0] * 20 + [500.0] * 5
        frame = pd.DataFrame({
            "Open": closes,
            "High": highs,
            "Low": lows,
            "Close": closes,
            "Volume": volumes,
        })

        metrics = _early_quality_metrics(frame)
        self.assertLessEqual(metrics["range_contraction"], 0.85)
        self.assertLessEqual(metrics["volume_dryup_ratio"], 0.80)

    def test_neutral_history_does_not_get_false_contraction(self):
        values = [100.0] * 25
        frame = pd.DataFrame({
            "Open": values,
            "High": [101.0] * 25,
            "Low": [99.0] * 25,
            "Close": values,
            "Volume": [1000.0] * 25,
        })

        metrics = _early_quality_metrics(frame)
        self.assertAlmostEqual(metrics["range_contraction"], 1.0)
        self.assertAlmostEqual(metrics["volume_dryup_ratio"], 1.0)


if __name__ == "__main__":
    unittest.main()
