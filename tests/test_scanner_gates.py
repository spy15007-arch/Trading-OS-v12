import unittest

from run_scan import final_quality_filter


def candidate(setup="FRESH BREAKOUT", **overrides):
    item = {
        "symbol": "TEST",
        "setup": setup,
        "score": 90,
        "price": 100.0,
        "entry": 100.0,
        "stop_loss": 95.0,
        "breakout_pct": 1.5 if setup == "FRESH BREAKOUT" else -1.0,
        "resistance": 98.5 if setup == "FRESH BREAKOUT" else 101.0,
        "rvol": 1.8 if setup == "FRESH BREAKOUT" else 0.85,
        "rsi": 62.0 if setup == "FRESH BREAKOUT" else 58.0,
        "extension": 3.0,
        "risk_pct": 5.0,
        "closing_strength": 0.82,
        "candle_body_ratio": 0.55,
        "upper_wick_ratio": 0.15,
        "base_range": 9.0,
        "compression": 12.0,
    }
    item.update(overrides)
    return item


class BreakoutGateTests(unittest.TestCase):
    def test_confirmed_fresh_breakout_passes(self):
        accepted = final_quality_filter([candidate()])
        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0]["setup"], "FRESH BREAKOUT")

    def test_fresh_breakout_with_weak_volume_is_rejected(self):
        accepted = final_quality_filter([candidate(rvol=1.1)])
        self.assertEqual(accepted, [])

    def test_fresh_breakout_with_rejection_wick_is_rejected(self):
        accepted = final_quality_filter([candidate(upper_wick_ratio=0.55)])
        self.assertEqual(accepted, [])

    def test_pre_breakout_near_resistance_passes(self):
        accepted = final_quality_filter([candidate(
            setup="PRE-BREAKOUT",
            price=100.0,
            entry=100.0,
            stop_loss=96.0,
            breakout_pct=-1.0,
            resistance=101.0,
            rvol=0.85,
            rsi=58.0,
            risk_pct=4.0,
        )])
        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0]["setup"], "PRE-BREAKOUT")

    def test_overextended_or_high_risk_candidate_is_rejected(self):
        rejected_extension = final_quality_filter([candidate(extension=11.0)])
        rejected_risk = final_quality_filter([candidate(risk_pct=9.0)])
        self.assertEqual(rejected_extension, [])
        self.assertEqual(rejected_risk, [])


if __name__ == "__main__":
    unittest.main()
